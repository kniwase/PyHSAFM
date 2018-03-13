# -*- coding: utf-8 -*-
import cv2, copy, math, csv, numpy as np, pandas as pd
from scipy import signal

from multiprocessing import Pool, Process
import multiprocessing as multi

#Class
class niwaImgInfo:
	def __init__(self, data, XYlength):
		self._XYlength = XYlength
		self._Zdata = np.array([data.min(), data.max()])
		self._shape = np.array(data.shape)
		self._lenppixel = self._XYlength[0] / self._shape[0]
		self._ns2ppixel = (self._XYlength[0]*self._XYlength[1]) / (self._shape[0]*self._shape[1])

	#accessors
	def __get_zdata(self):
		return self._Zdata
	def __set_zdata(self, value):
		raise NameError('zdata is read only')
	def __del_zdata(self):
		del self._Zdata
	zdata = property(__get_zdata, __set_zdata, __del_zdata)

	def __get_XYlength(self):
		return self._XYlength
	def __set_XYlength(self, value):
		raise NameError('XYlength is read only')
	def __del_XYlength(self):
		del self._XYlength
	XYlength = property(__get_XYlength, __set_XYlength, __del_XYlength)

	def __get_shape(self):
		return self._shape.copy()
	def __set_shape(self, value):
		raise NameError('shape is read only')
	def __del_shape(self):
		del self._shape
	shape = property(__get_shape, __set_shape, __del_shape)

	def __get_lenppixel(self):
		return self._lenppixel.copy()
	def __set_lenppixel(self, value):
		raise NameError('lenppixel is read only')
	def __del_lenppixel(self):
		del self._lenppixel
	lenppixel = property(__get_lenppixel, __set_lenppixel, __del_lenppixel)

	def __get_ns2ppixel(self):
		return self._ns2ppixel.copy()
	def __set_ns2ppixel(self, value):
		raise NameError('ns2ppixel is read only')
	def __del_ns2ppixel(self):
		del self._ns2ppixel
	ns2ppixel = property(__get_ns2ppixel, __set_ns2ppixel, __del_ns2ppixel)

class niwaImg(niwaImgInfo):
	def __init__(self, data, XYlength):
		self.__data = data.copy()
		self.__ori_data = data.copy()
		super(niwaImg, self).__init__(self.__ori_data, XYlength)

	#accessors
	def __get_data(self):
		return self.__data.copy()
	def __set_data(self, new_data):
		#if all([s1 == s2 for s1, s2 in zip(self.shape, new_data.shape)]):
		if list(self.shape) == list(new_data.shape):
			self.__data = new_data.copy()
		else:
			self.__data = cv2.resize(new_data, (self.shape[1], self.shape[0]))
		self._Zdata = np.array([self.__data.min(), self.__data.max()])
	def __del_data(self):
		del self.__data
	data = property(__get_data, __set_data, __del_data)

	def __get_ori_data(self):
		return self.__ori_data
	def __set_ori_data(self, new_data):
		raise NameError('Original data is read only')
	def __del_ori_data(self):
		del self.__ori_data
	ori_data = property(__get_ori_data, __set_ori_data, __del_ori_data)

	def copy(self):
		return copy.deepcopy(self)

	def getInfo(self):
		return niwaImgInfo(self)

	def getOpenCVimageGray(self):
		if (self.zdata[1] - self.zdata[0]) <= 0:
			print(self.zdata[1] - self.zdata[0])
		gray_img = (self.data - self.zdata[0]) / (self.zdata[1] - self.zdata[0])
		gray_img = np.uint8(gray_img * 255)
		return gray_img

	def getOpenCVimage(self):
		H = np.ones(self.shape, np.uint8)*19
		L = self.getOpenCVimageGray()
		S = np.ones(self.shape, np.uint8)*255
		img_color = np.dstack([H, L, S])
		return cv2.cvtColor(img_color, cv2.COLOR_HLS2BGR)

	def getHistogram(self, b = 256, o = 30):
		hist = np.histogram(self.__data, bins=b)
		peak = signal.argrelmax(hist[0], order=o)
		data = pd.DataFrame({'hist': pd.Series(hist[0]),
							 'bin_edges': pd.Series(hist[1][0:-1]),
							 'peak': pd.Series(peak[0])})
		return data

class movieWriter:
	def __init__(self, path, frame_time, imgShape):
		self.fourcc = cv2.VideoWriter_fourcc(*'avc1')
		self.fps = 1.0 / frame_time
		self.movieWriter = cv2.VideoWriter(path, self.fourcc, self.fps, (imgShape[1], imgShape[0]))

	def __enter__(self):
		return self.movieWriter

	def __exit__(self, type, value, traceback):
		print("   Saving Movie   ")
		self.movieWriter.release()

#functions
def readImg(path):
	csv_data = np.genfromtxt(path, delimiter=",", dtype='float')
	XYlength = np.array([csv_data[1][1], csv_data[1][3]], dtype=int)
	data = [row[1:-1] for row in csv_data[4:]]
	data = np.array(data[::-1])
	size_times = 3
	new_size = (XYlength[0]*size_times, XYlength[1]*size_times) #実際の長さベース
	data = cv2.resize(data, new_size)
	return niwaImg(data, XYlength)

def readInfo(path):
	src = readImg(path)
	return niwaImgInfo(src.data, src.XYlength)

def writeImg(path, img):
	cv2.imwrite(path, img.getImage())

def writeImgGray(path, img):
	cv2.imwrite(path, img.getImageGray())

#戻り値はniwaCV形式の画像
def binarize(src, lowest, highest = True):
	def __binarize(src, lowest):
		dst = src.copy()
		black = np.zeros(src.shape, dtype='float')
		white = black + 1.0
		dst.data = np.where(dst.data > lowest, white, black).astype("float")
		return dst

	if highest:
		dst = __binarize(src, lowest)
	else:
		mask1 = __binarize(src, lowest).data
		mask2 = cv2.bitwise_not(__binarize(src, highest).data)
		dst = src.copy()
		dst.data = cv2.bitwise_and(mask1, mask2)
	return dst

def heightCorrection(src, makeItZero = False, peak_num = 1, b = 512, o = 10):
	dst = src.copy()
	hist = np.histogram(dst.data, bins=b)
	peak = signal.argrelmax(hist[0], order=o)
	dst.data = dst.data - hist[1][peak[0][peak_num - 1]]
	if makeItZero:
		black = np.zeros_like(dst.data, dtype='uint8')
		dst.data = np.where(dst.data >= 0.0, dst.data, black)
	return dst

def heightScaling(src, highest):
	dst = src.copy()
	white = np.zeros(dst.shape, dtype='float') + highest
	dst.data = np.where(dst.data <= highest, dst.data, white)
	return dst

def writeTime(src, time, frame_num = ""):
	dst = src.copy()
	round=lambda x:(x*10.0*2+1)//2/10.0
	txt = str(round(time)) + "s"
	font = cv2.FONT_HERSHEY_DUPLEX
	font_size = 1.2
	position = (15, 45)
	dst = cv2.putText(dst, txt, position, font, font_size, (0, 0, 0), 6, cv2.LINE_AA)
	dst = cv2.putText(dst, txt, position, font, font_size, (255, 255, 255), 2, cv2.LINE_AA)
	if frame_num != "":
		txt = frame_num
		font = cv2.FONT_HERSHEY_DUPLEX
		position = (dst.shape[1] - 35, dst.shape[0]-4)
		font_size = 0.4
		dst = cv2.putText(dst, txt, position, font, font_size, (0, 0, 0), 2, cv2.LINE_AA)
		dst = cv2.putText(dst, txt, position, font, font_size, (255, 255, 255), 1, cv2.LINE_AA)
	return dst

class Kernels:
	sharp = lambda k = 1: np.matrix('0,{0},0;{0},{1},{0};0,{0},0'.format(-k,1+4*k))
	average = np.array([[1, 1, 1, 1, 1] for i in range(5)]) / 5**2
	gaussian = np.array([[1, 4, 6, 4, 1], [4, 16, 24, 16, 4], [6, 24, 36, 24, 6], [4, 16, 24, 16, 4], [1, 4, 6, 4, 1]], np.float32) / 4**4
	#laplacian = np.array([[1, 1, 1], [1, -8, 1], [1, 1, 1]], np.float32)
	laplacian = np.array([[-1, -3, -4, -3, -1], [-3, 0, 6, 0, -3], [-4, 6, 20, 6, -4], [-3, 0, 6, 0, -3], [-1, -3, -4, -3, -1]], np.float32)

def convolution_filter(src, kernel):
	dst = src.copy()
	dst.data = cv2.filter2D(src.data, -1, kernel)
	return dst

def find_edge(src):
	def normalize(img):
		return (img - img.min()) / (img.max() - img.min())
	dst = src.copy()
	gray = normalize(dst.data)
	#白い部分を膨張させる
	dilated = cv2.dilate(gray, np.ones((5, 5)), iterations=1)
	#差をとる
	dst.data = normalize(cv2.absdiff(dilated, gray))
	return dst

def enhance_edge(src, k = 10.0):
	def normalize(img):
		return (img - img.min()) / (img.max() - img.min())
	dst = src.copy()
	edge = normalize(convolution_filter(find_edge(src), Kernels.gaussian.data)
	dst.data -= (edge - 0.5) * k/10.0
	return dst

def median_filter(src, ksize = 5):
	d = int((ksize-1)/2)
	h, w = src.shape[0], src.shape[1]
	dst = src.copy()
	scr_data = src.data
	#近傍にある画素値の中央値を出力画像の画素値に設定
	dst.data = np.array([[np.median(scr_data[y-d:y+d+1, x-d:x+d+1]) for x in range(d, w-d)] for y in range(d, h-d)])
	return dst

def gaussian_filter(src):
	return convolution_filter(src, Kernels.gaussian)

def average_filter(src):
	return convolution_filter(src, Kernels.average)
