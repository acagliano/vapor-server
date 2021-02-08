import socket,threading,ctypes,hashlib,json,os,sys,time,math,traceback,logging,gzip
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

PORT=51000
BUFFER_SIZE=2048

ControlCodes={
    "MESSAGE":2,
    "FETCH_SOFTWARE_LIST":3,
    "FETCH_SERVER_LIST":4,
    "FETCH_SOFTWARE_INFO":5,
    "CHECK_FOR_UPDATES":6,
    "UPDATE_SOFTWARE":7
}

def PaddedString(s, amt, char=" "):
	if len(s)>=amt:
		return s[:amt]
	else:
		return s.ljust(amt, char)

def u16(*args):
	o=[]
	for arg in args:
		if int(arg)<0: arg = abs(int(arg))
		else: arg = int(arg)
		o.extend(list(int(arg).to_bytes(2,'little')))
	return o

class ClientDisconnectErr(Exception):
    pass

class ServerExit(Exception):
    pass

class GZipRotator:
    def __call__(self, source, dest):
        try:
            os.rename(source, dest)
            log_archive = f"logs/{datetime.now().year}-{datetime.now().month}_server.log.gz"
            with open(dest, 'rb') as f_in:
                with gzip.open(f"{log_archive}", 'ab') as f_out:
                    f_out.writelines(f_in)
            os.remove(dest)
        except:
            print(traceback.format_exc(limit=None, chain=True))
			
    
class Vapor:
    def __init__(self):
        # All directory constructs will omit trailing slash
        for dir in ["logs"]:
            try:
                os.makedirs(dir)
            except:
                pass
        try:
            # Init logging => To Console and to File
            self.logger = logging.getLogger("vapor.logger")
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(levelname)s: %(asctime)s: %(message)s')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            file_handler = TimedRotatingFileHandler("logs/vapor.log", when="midnight", interval=1, backupCount=5)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            file_handler.rotator = GZipRotator()
            self.logger.addHandler(file_handler)
        except:
            print(traceback.format_exc(limit=None, chain=True))
        
        # Begin server init
        try:
            self.clients={}
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(None)
            self.port = PORT
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', self.port))                 # Now wait for client connection.
            self.online=True
            self.main_thread = threading.Thread(target=self.main)
            self.main_thread.start()
            self.console()
        except:
            print(traceback.format_exc(limit=None, chain=True))
        
    def main(self):
        while self.online:
            try:
                self.sock.listen()
                conn, addr = self.sock.accept()
                self.emit_log(logging.INFO, f"Got new client from {addr}")
                #print( f"Got new client from {addr}")
                self.clients[conn] = client = Client(conn, addr, self)
                conn_thread = threading.Thread(target=client.handle_connection)
                conn_thread.start()
            except:
                print(traceback.format_exc(limit=None, chain=True))
                
    def emit_log(self, lvl, msg):
        try:
            self.logger.log(lvl, msg)
        except:
            print(traceback.format_exc(limit=None, chain=True))
            
    def console(self):
        while True:
            try:
                line = input("")
                print("[Console] "+line)
                if " " in line:
                    line = line.split(" ", 1)
                else:
                    line = [line]
                if line[0]=="list":
                    ostring=""
                    for c in self.clients.keys():
                        ostring+=f"{self.clients[c].ip}\n"
                    ostring+=f"{len(self.clients)} users connected!"
                    self.emit_log(logging.INFO, ostring)
                elif line[0]=="stop":
                    raise ServerExit()
            except (KeyboardInterrupt, ServerExit):
                self.emit_log(logging.INFO, "The server was stopped from Console")
                self.online=False
                break
            except:
                self.emit_log(traceback.format_exc(limit=None, chain=True))
                pass
            
class Client:
    def __init__(self, conn, addr, server):
        try:
            self.conn=conn
            self.addr=addr
            self.ip=addr[0]
            self.server=server
            self.send([ControlCodes["MESSAGE"]] + self.parse_string("Welcome to VAPOR"))
        except: self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
        
    def parse_string(self, str):
        try:
            return list(bytes(str+'\0', 'UTF-8'))
        except:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
        
    def send(self, data):
        packet_length = len(data)
        i = 0
        self.server.emit_log(logging.DEBUG, f"sending packet: {data}")
        try:
            while packet_length:
                bytes_sent = self.conn.send(bytes(data[i:min(packet_length, BUFFER_SIZE)]))
                if not bytes_sent:
                    raise Exception("packet transmission error")
                    break
                i+=bytes_sent
                packet_length-=bytes_sent
        except: self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
          
    def handle_connection(self):
        while self.server.online:
            try:
                data = list(self.conn.recv(BUFFER_SIZE))
                if not data:
                    raise ClientDisconnectErr(f"{self.ip} disconnected!")
                if not len(data):
                    continue
                elif data[0]==ControlCodes["FETCH_SOFTWARE_LIST"]:
                    self.get_software_avail()
                elif data[0]==ControlCodes["FETCH_SERVER_LIST"]:
                    self.get_servers()
                elif data[0]==ControlCodes["FETCH_SOFTWARE_INFO"]:
                    self.get_pkg_info()
                elif data[0]==ControlCodes["CHECK_FOR_UPDATES"]:
                    self.check_for_updates()
                elif data[0]==ControlCodes["UPDATE_SOFTWARE"]:
                    self.update_packages()
                else:
                    raise ClientDisconnectErr(f"Invalid packet ID from {self.ip}. User disconnected.")
            except ClientDisconnectErr as e:
                self.server.emit_log(logging.INFO, str(e))
                del self.server.clients[self.conn]
                self.conn.close()
                break
            except:
                self.server.emit_log(logging.INFO, traceback.format_exc(limit=None, chain=True))
   
    def get_software_avail(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
        
    def get_servers(self):
        odata=[]
        for obj in os.scandir("/home/servers/services/"):
            if obj.is_dir():
                srv_name=os.path.basename(obj.name)
                print(obj.name)
                srv_name_padded=PaddedString(srv_name, 16, chr(0))
                odata+=self.parse_string(srv_name_padded)
            with open(f"/home/servers/services/{obj.name}/service.conf") as f:
                cfg=json.load(f)
                port=cfg["port"]
                odata+=u16(port)
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                location = ("127.0.0.1", port)
                if temp_socket.connect_ex(location)==0:
                    odata.append(True)
                else:
                    odata.append(False)
                temp_socket.close()
        self.send([ControlCodes["FETCH_SERVER_LIST"]] + odata)
        
    def get_pkg_info(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
        
    def check_for_updates(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
        
    def update_packages(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
                                                

if __name__ == '__main__':
	
	server = Vapor()
                                    
        
