import socket,threading,ctypes,hashlib,json,os,sys,time,math,traceback,re,ipaddress,random

ControlCodes={
    "FETCH_SOFTWARE_LIST":2,
    "FETCH_SERVER_LIST":3,
    "CHECK_FOR_UPDATES":4
}

class ClientDisconnectErr(Exception):
  pass
    
class Vapor:
  def
