#!/usr/bin/python
import os
import sys
import json
import time
if sys.version_info[0] < 3:
	import thread
else:
	import _thread
import threading
import socket

from flask import Flask, render_template, jsonify, Response, request
import logging

import MkSGlobals
from mksdk import MkSFile
from mksdk import MkSAbstractNode
from mksdk import MkSLogger

class SlaveNode(MkSAbstractNode.AbstractNode):
	def __init__(self):
		MkSAbstractNode.AbstractNode.__init__(self)
		self.ClassName								= "Slave Node"
		self.MasterNodesList						= [] # For future use (slave to slave communication)
		self.SlaveListenerPort 						= 0
		self.MasterInfo 							= None
		self.MasterUUID 							= ""
		self.IsLocalUIEnabled						= False
		# Sates
		self.States 								= {
			'IDLE': 								self.State_Idle,
			'INIT':									self.State_Init,
			'CONNECT_MASTER':						self.State_ConnectMaster,
			'FIND_PORT_MANUALY':					self.State_FindPortManualy,
			'GET_MASTER_INFO':						self.State_GetMasterInfo,
			'GET_PORT': 							self.State_GetPort,
			'WAIT_FOR_PORT':						self.State_WaitForPort,
			'START_LISTENER':						self.State_StartListener,
			'WORKING':								self.State_Working,
			'EXIT':									self.State_Exit
		}
		# Handlers
		self.NodeResponseHandlers['get_port'] 		= self.GetPortResponseHandler
		self.NodeRequestHandlers['shutdown'] 		= self.ShutdownRequestHandler
		# Callbacks
		self.OnGetNodeInfoCallback 					= None
		self.OnGetSensorInfoRequestCallback			= None
		self.OnSetSensorInfoRequestCallback 		= None
		# Flags
		self.IsListenerEnabled 						= False
		# Counters
		self.MasterConnectionTries 					= 0
		self.MasterInformationTries 				= 0
		self.MasterTickTimeout 						= 4
		self.EnableLog								= True

	''' 
		Description: 	N/A
		Return: 		N/A
	'''	
	def EnableLogs(self, name):
		self.Logger = MkSLogger.Logger(name)
		self.Logger.EnablePrint()
		self.Logger.SetLogLevel(self.System["log_level"])
		if "log_to_file" in self.System:
			if self.System["log_to_file"] == "True":
				self.Logger.EnableLogger()

	''' 
		Description: 	State [IDLE]
		Return: 		None
	'''	
	def State_Idle(self):
		self.LogMSG("({classname})# Note, in IDLE state ...".format(classname=self.ClassName),1)
		time.sleep(1)

	''' 
		Description: 	State [INIT]
		Return: 		None
	'''		
	def State_Init (self):
		self.MasterConnectionTries	= 0
		self.MasterInformationTries	= 0	
		self.SetState("CONNECT_MASTER")

	''' 
		Description: 	State [CONNECT_MASTER]
		Return: 		None
	'''	
	def State_ConnectMaster(self):
		if 0 == self.Ticker % self.MasterTickTimeout or 0 == self.MasterConnectionTries:
			if self.MasterConnectionTries > 3:
				self.SetState("EXIT")
				# self.SetState("FIND_PORT_MANUALY")
			else:
				self.LogMSG("({classname})# Trying to connect Master ({tries}) ...".format(classname=self.ClassName, tries=self.MasterConnectionTries),1)
				if self.ConnectLocalMaster() is True:
					self.SetState("GET_MASTER_INFO")
					self.SocketServer.Start()
				else:
					self.SetState("CONNECT_MASTER")
					self.MasterConnectionTries += 1

	''' 
		Description: 	State [GET_MASTER_INFO]
		Return: 		None
	'''		
	def State_GetMasterInfo(self):
		if 0 == self.Ticker % 10 or 0 == self.MasterInformationTries:
			if self.MasterInformationTries > 3:
				self.SetState("EXIT")
				# self.SetState("FIND_PORT_MANUALY")
			else:
				self.LogMSG("({classname})# Send <get_node_info> request ...".format(classname=self.ClassName),5)
				# Send request
				message = self.BasicProtocol.BuildRequest("DIRECT", "MASTER", self.UUID, "get_node_info", {}, {})
				packet  = self.BasicProtocol.AppendMagic(message)
				if self.LocalMasterConnection is not None:
					self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)
				self.MasterInformationTries += 1

	''' 
		Description: 	State [GET_PORT]
		Return: 		None
	'''	
	def State_GetPort(self):
		self.LogMSG("({classname})# Sending <get_port> request ...".format(classname=self.ClassName),5)
		# Send request
		message = self.BasicProtocol.BuildRequest("DIRECT", self.MasterUUID, self.UUID, "get_port", self.NodeInfo, {})
		packet  = self.BasicProtocol.AppendMagic(message)
		if self.LocalMasterConnection is not None:
			self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)
		self.SetState("WAIT_FOR_PORT")

	''' 
		Description: 	State [FIND_PORT_MANUALY] (This state disabled for now)
		Return: 		None
	'''		
	def State_FindPortManualy(self):
		self.LogMSG("({classname})# Trying to find port manualy ...".format(classname=self.ClassName),5)
		if self.SlaveListenerPort == 0:
			for idx in range(1,33):
				port = 10000 + idx
				sock, status = self.SocketServer.Connect((self.MyLocalIP, port))
				if status is True:
					self.SlaveListenerPort = port
					self.SetState("START_LISTENER")
					return
				else:
					sock.close()
		else:
			self.SetState("START_LISTENER")

	''' 
		Description: 	State [WAIT_FOR_PORT]
		Return: 		None
	'''	
	def State_WaitForPort(self):
		if 0 == self.Ticker % 20:
			if 0 == self.SlaveListenerPort:
				self.SetState("GET_PORT")
			else:
				self.SetState("START_LISTENER")

	''' 
		Description: 	State [START_LISTENER]
		Return: 		None
	'''	
	def State_StartListener(self):
		self.LogMSG("({classname})# [State_StartListener]".format(classname=self.ClassName),5)
		self.SocketServer.EnableListener(self.SlaveListenerPort)
		self.SocketServer.StartListener()
		# Let socket listener start
		time.sleep(0.1)
		# Update connection database.
		conn = self.SocketServer.GetConnectionBySock(self.SocketServer.GetListenerSocket())
		conn.Obj["listener_port"] = self.SocketServer.GetListenerPort()
		# Change state
		self.SetState("WORKING")
		self.StartLocalWebsocketServer(self.SocketServer.GetListenerPort() + 2000)
		
	''' 
		Description: 	State [WORKING]
		Return: 		None
	'''		
	def State_Working(self):
		if self.SocketServer.GetListenerStatus() is True:
			if self.SystemLoaded is False:
				self.SystemLoaded = True # Update node that system done loading.
				if self.NodeSystemLoadedCallback is not None:
					try:
						self.NodeSystemLoadedCallback()
					except Exception as e:
						self.LogException("[State_Work] NodeSystemLoadedCallback",e,3)
			
			if 0 == self.Ticker % 60:
				self.SendGatewayPing()

	''' 
		Description: 	State [EXIT]
		Return: 		None
	'''	
	def State_Exit(self):
		self.Exit("Exit state initiated")
	
	''' 
		Description: 	N/A
		Return: 		N/A
	'''	
	def LocalNetworkBroadcastHandler(self, connection, raw_data):
		self.LocalNetworkMessageHandler(connection, raw_data)

	''' 
		Description: 	N/A
		Return: 		N/A
	'''	
	def LocalNetworkMessageHandler(self, connection, raw_data):
		packet 		= json.loads(raw_data)
		dest 		= self.BasicProtocol.GetDestinationFromJson(packet)

		if dest in [self.UUID, "BROADCAST"]:
			sock 		= connection.Socket
			msg_type 	= self.BasicProtocol.GetMessageTypeFromJson(packet)
			cmd 		= self.BasicProtocol.GetCommandFromJson(packet)
			direct 		= self.BasicProtocol.GetDirectionFromJson(packet)
			src 		= self.BasicProtocol.GetSourceFromJson(packet)

			if direct in "request":
				if cmd in self.NodeRequestHandlers.keys():
					try:
						handler = self.NodeRequestHandlers[cmd]
						if handler is not None:
							# Execute framework layer
							message = handler(sock, packet)
							# This handler migth be also in application layer.
							if cmd in self.NodeFilterCommands:
								if self.OnApplicationRequestCallback is not None:
									# Execute application layer
									message = self.OnApplicationRequestCallback(sock, packet)
							# In any case response messgae is empty, don't send response
							if message == "" or message is None:
								return
							# Create response and send back to requestor
							msg_response = self.BasicProtocol.BuildResponse(packet,message)
							packet = self.BasicProtocol.AppendMagic(msg_response)
							self.SocketServer.Send(sock, packet)
					except Exception as e:
						self.LogException("[LocalNetworkMessageHandler] {0}".format(cmd),e,3)
				else:
					# This command belongs to the application level
					if self.OnApplicationRequestCallback is not None:
						try:
							message = self.OnApplicationRequestCallback(sock, packet)
							if message == "" or message is None:
								return
							# Create response and send back to requestor
							msg_response = self.BasicProtocol.BuildResponse(packet,message)
							# self.LogMSG("({classname})# [LocalNetworkMessageHandler] Sending RESPONSE\n{0}".format(msg_response,classname=self.ClassName),5)
							packet = self.BasicProtocol.AppendMagic(msg_response)
							self.SocketServer.Send(sock, packet)
						except Exception as e:
							self.LogException("[DataSocketInputHandler #2]",e,3)
			elif direct in "response":
				if cmd in self.NodeResponseHandlers.keys():
					try:
						handler = self.NodeResponseHandlers[cmd](sock, packet)
						if handler is not None:
							# Execute framework layer
							handler(sock, packet)
							# This handler migth be also in application layer.
							if cmd in self.NodeFilterCommands:
								if self.OnApplicationRequestCallback is not None:
									# Execute application layer
									self.OnApplicationRequestCallback(sock, packet)
					except Exception as e:
						self.LogException("[LocalNetworkMessageHandler] {0}".format(cmd),e,3)
				else:
					# This command belongs to the application level
					if self.OnApplicationResponseCallback is not None:
						try:
							self.OnApplicationResponseCallback(sock, packet)
						except Exception as e:
							self.LogException("[LocalNetworkMessageHandler]",e,3)
			elif direct in "message":
				if self.OnNoneDirectionMessageArrivedCallback is not None:
					payload = self.BasicProtocol.GetPayloadFromJson(packet)
					self.OnNoneDirectionMessageArrivedCallback(cmd, src, payload)
			else:
				pass

	''' 
		Description: 	Handler [get_node_info] REQUEST
		Return: 		N/A
	'''	
	def GetNodeInfoRequestHandler(self, sock, packet):
		self.LogMSG("({classname})# [GetNodeInfoRequestHandler] Return NODE information".format(classname=self.ClassName),5)
		conn 	= self.SocketServer.GetConnectionBySock(sock)
		payload = self.NodeInfo

		payload["is_master"] 		= False
		payload["master_uuid"] 		= self.MasterUUID
		payload["pid"]				= self.MyPID
		payload["listener_port"]	= self.SocketServer.GetListenerPort()
		payload["ip"] 				= self.MyLocalIP

		src = self.BasicProtocol.GetSourceFromJson(packet)
		if src not in ["WEBFACE"]:
			if conn.Kind is "SERVER":
				payload["port"] = conn.Obj["server_port"]
			elif conn.Kind is "CLIENT":
				payload["port"] = conn.Obj["client_port"]
		
		return payload

	''' 
		Description: 	Handler [get_node_info] RESPONSE
		Return: 		N/A
	'''	
	def GetNodeInfoResponseHandler(self, sock, packet):
		source  	= self.BasicProtocol.GetSourceFromJson(packet)
		payload 	= self.BasicProtocol.GetPayloadFromJson(packet)
		additional 	= self.BasicProtocol.GetAdditionalFromJson(packet)
		# self.LogMSG("({classname})# [GetNodeInfoResponseHandler] [{0}, {1}, {2}, {3}, {4}]".format(source,payload["uuid"],payload["type"],payload["pid"],payload["name"], classname=self.ClassName),5)

		if source in "MASTER":
			conn = self.SocketServer.GetConnectionBySock(sock)
			if conn is not None:
				conn.Obj["uuid"] 			= payload["uuid"]
				conn.Obj["type"] 			= payload["type"]
				conn.Obj["pid"] 			= payload["pid"]
				conn.Obj["name"] 			= payload["name"]
				conn.Obj["listener_port"]	= payload["listener_port"]
				conn.Obj["status"] 	= 1

				if self.GetState() in "GET_MASTER_INFO":
					# We are here because this is a response for slave boot sequence
					self.MasterInfo = payload
					self.MasterUUID = payload["uuid"]
					self.SetState("GET_PORT")
				else:
					if self.OnGetNodeInfoCallback is not None:
						self.OnGetNodeInfoCallback(payload)
		else:
			# self.LogMSG("({classname})# [GetNodeInfoResponseHandler] [{0}]".format(payload, classname=self.ClassName),5)
			conn = self.SocketServer.GetConnection(payload["ip"], payload["port"])
			if conn is not None:
				conn.Obj["uuid"] 			= payload["uuid"]
				conn.Obj["type"] 			= payload["type"]
				conn.Obj["pid"] 			= payload["pid"]
				conn.Obj["name"] 			= payload["name"]
				conn.Obj["listener_port"]	= payload["listener_port"]
				conn.Obj["status"] 	= 1
				if self.OnGetNodeInfoCallback is not None:
					self.OnGetNodeInfoCallback(payload)

	''' 
		Description: 	Handler [get_port] RESPONSE
		Return: 		N/A
	'''		
	def GetPortResponseHandler(self, sock, packet):
		source  = self.BasicProtocol.GetSourceFromJson(packet)
		payload = self.BasicProtocol.GetPayloadFromJson(packet)
		self.LogMSG("({classname})# [GetPortResponseHandler]".format(classname=self.ClassName),5)

		if source in self.MasterUUID:
			self.SlaveListenerPort = payload["port"]
			self.SetState("START_LISTENER")

	''' 
		Description: 	[HANDLERS]
		Return: 		N/A
	'''	
	def GetNodeStatusRequestHandler(self, sock, packet):
		self.LogMSG("({classname})# [GetNodeStatusRequestHandler]".format(classname=self.ClassName),5)
		payload = {
			"status":"online",
			"state": self.State,
			"info": self.NodeInfo
		}
		return payload

	''' 
		Description: 	Override method to send request
		Return: 		N/A
	'''	
	def SendRequest(self, uuid, msg_type, command, payload, additional):
		# Generate request
		message = self.BasicProtocol.BuildRequest(msg_type, uuid, self.UUID, command, payload, additional)
		packet  = self.BasicProtocol.AppendMagic(message)
		# If slave connected via direct socket
		node = self.GetNodeByUUID(uuid)
		if node is not None:
			self.SocketServer.Send(node.Socket, packet)
		else:
			# Send via MASTER
			if self.LocalMasterConnection is not None:
				self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)
	
	''' 
		Description: 	Override method to send request
		Return: 		N/A
	'''	
	def SendReponse(self, uuid, msg_type, command, payload, additional):
		# Generate request
		message = self.BasicProtocol.CreateResponse(msg_type, uuid, self.UUID, command, payload, additional)
		packet  = self.BasicProtocol.AppendMagic(message)
		# If slave connected via direct socket
		node = self.GetNodeByUUID(uuid)
		if node is not None:
			self.SocketServer.Send(node.Socket, packet)
		else:
			# Send via MASTER
			if self.LocalMasterConnection is not None:
				self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)
	
	''' 
		Description: 	Emit event to webface.
		Return: 		N/A
	'''		
	def EmitOnNodeChangeByIndex(self, index, data):
		self.DeviceChangeListLock.acquire()
		# Itterate over registered nodes.
		for item in self.OnDeviceChangeList:
			payload 		= item["payload"]
			item_type		= payload["item_type"]
			destination		= ""

			# Send to Node
			if item_type == 1:
				destination = payload["uuid"]
				self.LogMSG("({classname})# [EmitOnNodeChangeByIndex] NODE {0}".format(destination,classname=self.ClassName),5)
				self.SendReponse(destination, "DIRECT", "operations", {
					"index": 	 index,
					"subindex":	 0x100,
					"direction": 0x1,
					"data": data
				}, {})
		self.DeviceChangeListLock.release()

	''' 
		Description: 	Emit event to webface.
		Return: 		N/A
	'''		
	def EmitOnNodeChange(self, data):
		self.DeviceChangeListLock.acquire()
		# Itterate over registered nodes.
		for item in self.OnDeviceChangeList:
			payload 		= item["payload"]
			item_type		= payload["item_type"] # (1 - Node, 2 - Webface)
			destination		= ""
			event_payload	= {}

			# Node
			if item_type == 1:
				destination = payload["uuid"]
			# Webface
			elif item_type in [2,3]:
				destination = "WEBFACE"
				# The connected socket is via gateway.
				if payload["pipe"] == "GATEWAY":
					event_payload = {
						'identifier':-1,
						'webface_indexer':payload["webface_indexer"]
					}
				# The connected socket is via local websocket.
				elif payload["pipe"] == "LOCAL_WS":
					event_payload = {
						'identifier':-1
					}

			# Send to Node
			if item_type == 1:
				self.LogMSG("({classname})# [EmitOnNodeChange] NODE {0}".format(destination,classname=self.ClassName),5)
				self.SendReponse(destination, "DIRECT", "on_node_change", data, event_payload)
			# Send via Master or Local Websocket
			elif item_type == 2:
				# Build message
				self.LogMSG("({classname})# [EmitOnNodeChange] MASTER {0}".format(destination,classname=self.ClassName),5)
				message = self.BasicProtocol.BuildRequest("DIRECT", destination, self.UUID, "on_node_change", data, event_payload)
				if self.IsLocalSockInUse is True:
					self.EmitEventViaLocalWebsocket(message)
				else:
					if self.LocalMasterConnection is not None:
						packet  = self.BasicProtocol.AppendMagic(message)
						self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)
			# Local WebSocket Server (LOCAL UI ENABLED) - Disabled
			elif item_type == 3:
				self.LogMSG("({classname})# [EmitOnNodeChange] DISABLED {0}".format(destination,classname=self.ClassName),5)
				pass
			else:
				self.LogMSG("({classname})# [EmitOnNodeChange] UNSUPPORTED {0}".format(destination,classname=self.ClassName),5)
		self.DeviceChangeListLock.release()

	''' 
		Description: 	Send <ping> request to gateway with node information.
		Return: 		N/A
	'''		
	def SendGatewayPing(self):
		# Send request
		message = self.BasicProtocol.BuildRequest("DIRECT", "GATEWAY", self.UUID, "ping", self.NodeInfo, {})
		packet  = self.BasicProtocol.AppendMagic(message)

		if self.LocalMasterConnection is not None:
			self.LogMSG("({classname})# Sending ping request ...".format(classname=self.ClassName),1)
			self.SocketServer.Send(self.LocalMasterConnection.Socket, packet)

	''' 
		Description: 	Local handler - Node disconnected event.
		Return: 		N/A
	'''		
	def NodeDisconnectedHandler(self, connection):
		self.LogMSG("({classname})# [NodeDisconnectedHandler]".format(classname=self.ClassName),5)
		# Check if disconneced connection is a master.
		for node in self.MasterNodesList:
			if connection.Socket == node.Socket:
				self.MasterNodesList.remove(node)
				# Need to close listener port because we are going to get this port again
				self.LocalMasterConnection.Socket.close()
				# If master terminated we need to close node.
				self.SetState("CONNECT_MASTER")
				self.LocalMasterConnection = None
				if self.OnMasterDisconnectedCallback is not None:
					self.OnMasterDisconnectedCallback()
		else:
			# Raise event for user
			if self.OnTerminateConnectionCallback is not None:
				self.OnTerminateConnectionCallback(connection)

	''' 
		Description: 	List of masters.
		Return: 		List of masters.
	'''			
	def GetMasters(self):
		return self.MasterNodesList

	''' 
		Description: 	Handler [get_node_status] RESPONSE
		Return: 		N/A
	'''		
	def GetNodeStatusResponseHandler(self, sock, packet):
		if self.OnApplicationResponseCallback is not None:
			self.OnApplicationResponseCallback(sock, packet)

	''' 
		Description: 	Handler [shutdown] REQUEST
		Return: 		N/A
	'''
	def ShutdownRequestHandler(self, sock, packet):
		self.LogMSG("({classname})# [ShutdownRequestHandler]".format(classname=self.ClassName),5)
		source  = self.BasicProtocol.GetSourceFromJson(packet)
		self.LogMSG("({classname})# [ShutdownRequestHandler] {0} {1}".format(source,self.MasterUUID,classname=self.ClassName),5)
		if source in self.MasterUUID:
			try:
				if self.OnShutdownCallback is not None:
					self.OnShutdownCallback()
			except Exception as e:
				self.LogException("[ShutdownRequestHandler]",e,3)

			# Send message to requestor.
			message = self.BasicProtocol.BuildResponse(packet, {"status":"shutdown"})
			packet  = self.BasicProtocol.AppendMagic(message)
			# Let the messsage propogate to local server.
			time.sleep(1)
			self.Exit("Shutdown request received")
		else:
			# Send message to requestor.
			message = self.BasicProtocol.BuildResponse(packet, {"status":"working"})
			packet  = self.BasicProtocol.AppendMagic(message)	
		self.SocketServer.Send(sock, packet)

		return None		
