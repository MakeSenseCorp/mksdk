#!/usr/bin/python
import os
import sys
import time
import struct
import json
import queue
if sys.version_info[0] < 3:
	import _thread
else:
	import _thread
import threading

from mksdk import MkSUSBAdaptor
from mksdk import MkSProtocol
from mksdk import MkSAbstractConnector

class Connector (MkSAbstractConnector.AbstractConnector):
	def __init__ (self):
		MkSAbstractConnector.AbstractConnector.__init__(self)
		self.ClassName 						= "Connector"
		self.NodeType 						= 0
		self.Adapters						= []
		self.Protocol 						= MkSProtocol.Protocol()
		self.UARTInterfaces 				= []
		self.RecievePacketsWorkerRunning	= False
		# Events
		self.AdaptorDisconnectedEvent 		= None
		self.AdaptorAsyncDataEvent 			= None
		# Data arrived queue
		self.QueueLock      	    		= threading.Lock()
		self.Packets      					= queue.queue()

		_thread.start_new_thread(self.RecievePacketsWorker, ())
	
	def RecievePacketsWorker (self):
		self.RecievePacketsWorkerRunning = True
		while self.RecievePacketsWorkerRunning == True:
			try:
				item = self.Packets.get(block=True,timeout=None)
				if self.AdaptorAsyncDataEvent is not None:
					self.AdaptorAsyncDataEvent(item["path"], item["data"])
			except Exception as e:
				print ("({classname})# [ERROR] (RecievePacketsWorker) {0}".format(str(e), classname=self.ClassName))

	def FindUARTDevices(self):
		dev = os.listdir("/dev/")
		return ["/dev/" + item for item in dev if "ttyUSB" in item]
	
	def __Connect(self, path):
		adaptor = MkSUSBAdaptor.Adaptor(path, 9600)
		adaptor.OnSerialAsyncDataCallback 			= self.OnAdapterDataArrived
		adaptor.OnSerialConnectionClosedCallback 	= self.OnAdapterDisconnected
		status = adaptor.Connect(3)
		if status is True:
			tx_packet = self.Protocol.GetDeviceTypeCommand()
			rx_packet = adaptor.Send(tx_packet)
			if (len(rx_packet) > 3):
				deviceType = ''.join([str(unichr(elem)) for elem in rx_packet[3:]])
				if str(deviceType) == str(self.NodeType):
					self.Adapters.append({
						'dev': adaptor,
						'path': path
					})
					return True
			adaptor.Disconnect()
		return False
	
	def Connect (self, device_type):
		self.NodeType = device_type
		self.UARTInterfaces = self.FindUARTDevices()
		for dev_path in self.UARTInterfaces:
			# Try for 3 times
			for i in range(3):
				if self.__Connect(dev_path) is True:
					break
		return self.Adapters
	
	def FindAdaptor(self, path):
		for adaptor in self.Adapters:
			if adaptor["path"] == path:
				return adaptor
		return None
	
	def UpdateUARTInterfaces(self):
		changes = []
		interfaces = self.FindUARTDevices()
		# Find disconnected adaptors
		for adaptor in self.Adapters:
			if adaptor["path"] not in interfaces:
				# USB must be disconnected
				changes.append({
					"change": "remove",
					"path": adaptor["path"]
				})
		for interface in interfaces:
			adaptor = self.FindAdaptor(interface)
			if adaptor is None:
				if self.__Connect(interface) is True:
					changes.append({
						"change": "append",
						"path": interface
					})

		if len(changes) > 0:
			print ("({classname})# Changes ({0})".format(changes, classname=self.ClassName))
		
		return changes
	
	def OnAdapterDisconnected(self, path):
		adaptor = self.FindAdaptor(path)
		if self.AdaptorDisconnectedEvent is not None and adaptor is not None:
			if "rf_type" in adaptor:
				self.AdaptorDisconnectedEvent(path, adaptor["rf_type"])
		if adaptor is not None:
			self.Adapters.remove(adaptor)

	def OnAdapterDataArrived(self, path, data):
		if len(data) > 3:
			self.QueueLock.acquire()			
			self.Packets.put( {
				'path': path,
				'data': data
			})
			self.QueueLock.release()
		else:
			print ("({classname})# (OnAdapterDataArrived) Data length not meet the required ({0})".format(len(data), classname=self.ClassName))
	
	def Disconnect(self):
		self.IsConnected = False
		self.RecievePacketsWorkerRunning = False
		while len(self.Adapters) > 0:
			for adaptor in self.Adapters:
				print ("({classname})# Adaptor close [{0}]".format(adaptor["path"], classname=self.ClassName))
				adaptor["dev"].Disconnect()
		

	def IsValidDevice(self):
		return self.IsConnected
	
	def GetUUID (self):
		txPacket = self.Protocol.GetDeviceUUIDCommand()
		rxPacket = self.Adaptor.Send(txPacket)
		return rxPacket[6:-1] # "-1" is for removing "\n" at the end (no unpack used)

	def Send(self, packet):
		pass
