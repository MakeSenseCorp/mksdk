#!/usr/bin/python
import os
import sys
import hashlib

class Security():
	def __init__(self):
		pass
	
	def GetMD5Hash(self, content):
		md5Obj = hashlib.md5(content.encode())
		hash = md5Obj.hexdigest()
		return hash
		# For Python 3+ hashlib.md5("whatever your string is".encode('utf-8')).hexdigest()