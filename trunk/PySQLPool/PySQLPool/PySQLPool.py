"""
@author: Nick Verbeck
@since: date 5/12/2008
@version: 0.2
"""

import MySQLdb, thread, md5
from threading import Condition
from PySQLConnection import PySQLConnectionManager

class PySQLPool(object):
	"""
	MySQL Connection Pool Manager
	
	This is the heart of the PySQLPool Library. The borg pattern is used here to store connections and manage the connections.
	
	@author: Nick Verbeck
	@since: 5/18/2008
	@version: 0.2
	"""
	
	#Dictionary used for storing all Connection information
	__Pool = {}
	
	#Max Connections that can be opened among all connections
	maxActiveConnections = 10
	
	#Max Active Query objects against 1 connection
	maxActivePerConnection = 2
	
	def __init__(self):
		"""
		Constructor for PySQLPool
		
		@author: Nick Verbeck
		@since: 5/12/2008
		"""
		self.__dict__ = self.__Pool
		
		if not self.__Pool.has_key('lock'):
			self.__Pool['lock'] = Condition()
			
		if not self.__Pool.has_key('conn'):
			self.__Pool['conn'] = {}
		
	def Terminate(self):
		"""
		Close all open connections
		
		Loop though all the connections and commit all queries and close all the connections. 
		This should be called at the end of your application.
		
		@author: Nick Verbeck
		@since: 5/12/2008
		"""
		self.Commit()
		for key in self.__Pool['conn']:
			try:
				for conn in self.__Pool['conn'][key]:
					try:
						self.__Pool['conn'][key][conn].Close()
					except Exception, e:
						pass
			except Exception, e:
				pass
		self.__Pool['conn'] = {}
		
	def Cleanup(self):
		"""
		Cleanup Timed out connections
		
		Loop though all the connections and test if still active. If inactive close socket.
		
		@author: Nick Verbeck
		@since: 2/20/2009
		"""
		self.Commit()
		for key in self.__Pool['conn']:
			try:
				for conn in self.__Pool['conn'][key]:
					try:
						self.__Pool['conn'][key][conn].TestConnection()
					except Exception, e:
						pass
			except Exception, e:
				pass
		self.__Pool['conn'] = {}
			
	def Commit(self):
		"""
		Commits all currently open connections
		
		@author: Nick Verbeck
		@since: 9/12/2008
		"""
		for key in self.__Pool['conn']:
			try:
				for conn in self.__Pool['conn'][key]:
					try:
						self.__Pool['conn'][key][conn].Commit()
					except Exception, e:
						pass
			except Exception, e:
				pass
		
	def GetConnection(self, PySQLConnectionObj):
		"""
		Get a Open and active connection
		
		Returns a PySQLConnectionManager is one is open else it will create a new one if the max active connections hasn't been hit.
		If all possible connections are used. Then None is returned.
		
		@param PySQLConnectionObj: PySQLConnection Object representing your connection string
		@author: Nick Verbeck
		@since: 5/12/2008   
		"""
		
		#Lock the Connection Collection/Pool
		self.__Pool['lock'].acquire()
		
		key = PySQLConnectionObj.key
		
		connection = None
		
		if self.__Pool['conn'].has_key(key):
			for i in self.__Pool['conn'][key]:
				#Grab an active connection if maxActivePerConnection is not meet
				if self.__Pool['conn'][key][i].activeConnections <= self.maxActivePerConnection:
					self.__Pool['conn'][key][i].lock.acquire()
					if self.__Pool['conn'][key][i].TestConnection() is False:
						self.__Pool['conn'][key][i].ReConnect()
					self.__Pool['conn'][key][i].lock.release()
					connection = self.__Pool['conn'][key][i]
				#Force Release a connection if the query has been completed. 
				#This solves a bug where some threaded apps would run faster then the pool could reallocate the connection. - Nick Verbeck
				elif self.__Pool['conn'][key][i].query is None:
					self.__Pool['conn'][key][i].lock.acquire()
					self.__Pool['conn'][key][i].count = 0
					if self.__Pool['conn'][key][i].TestConnection() is False:
						self.__Pool['conn'][key][i].ReConnect()
					self.__Pool['conn'][key][i].lock.release()
					connection = self.__Pool['conn'][key][i]
					
			if connection is None:
				#Create a new Connection is Max Connections is not meet
				connKey = len(self.__Pool['conn'][key])
				if connKey > self.maxActiveConnections:
					connection = None
				else:
					self.__Pool['conn'][key][connKey] = PySQLConnectionManager(PySQLConnectionObj)
					connection = self.__Pool['conn'][key][connKey]
		#Create new Connection Pool Set
		else:
			self.__Pool['conn'][key] = {}
			self.__Pool['conn'][key][0] = PySQLConnectionManager(PySQLConnectionObj)
			connection = self.__Pool['conn'][key][0]
		
		if connection is not None:	
			connection.activeConnections += 1
			
		self.__Pool['lock'].release()
		return connection
	
	def returnConnection(self, connObj):
		"""
		Return connection back to the pool for reuse.
		
		@author: Nick Verbeck
		@since: 5/12/2008
		"""
		connObj.activeConnections -= 1
		connObj.query = None
		