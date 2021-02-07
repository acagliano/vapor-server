import socket,threading,ctypes,hashlib,json,os,sys,time,math,traceback,re,ipaddress,random,logigng

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
        
        # Init logging => To Console and to File
        self.logger = logging.getLogger("vapor")
        formatter = logging.Formatter('%(levelname)s: %(asctime)s: %(message)s')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        file_handler = TimedRotatingFileHandler("logs/vapor.log", when="midnight", interval=1, backupCount=5)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        file_handler.rotator = GZipRotator()
        self.logger.addHandler(file_handler)
        
        # Begin server init
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(None)
        self.port = PORT
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.port))                 # Now wait for client connection.
        self.online=True
        self.main_thread = threading.Thread(target=self.main)
        self.main_thread.start()
        self.console()
        
    def main(self):
        while self.online:
            try:
                self.sock.listen()
                conn, addr = self.sock.accept()
                self.log(logging.INFO, f"Got new client from {addr}")
                self.clients[conn] = client = Client(conn, addr, self)
                conn_thread = threading.Thread(target=client.handle_connection)
                conn_thread.start()
            except:
                self.log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
                
    def log(self, lvl, msg):
        self.logger.log(lvl, msg)         
            
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
                    self.log(logging.INFO, ostring)
                elif line[0]=="stop":
                    raise ServerExit()
            except (KeyboardInterrupt, ServerExit) as e:
                self.server.log(logging.INFO, "The server was stopped from Console")
                self.online=False
                break
            except:
                print(traceback.format_exc(limit=None, chain=True))
            
class Client:
    def __init__(self, conn, addr, server):
        self.conn=conn
        self.addr=addr
        self.ip=addr[0]
        self.server=server
        self.send([ControlCodes["MESSAGE"]] + list("Welcome to VAPOR\0"))
        
    def send(self, data):
        packet_length = len(data)
		i = 0
		try:
			while packet_length:
				bytes_sent = self.conn.send(bytes(data[i:min(packet_length, BUFFER_SIZE)]))
				if not bytes_sent:
					raise Exception("packet transmission error")
					break
				i+=bytes_sent
				packet_length-=bytes_sent
		except: self.server.log(logging.ERROR, f"conn.send() error for Client at {self.ip}")
          
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
                self.server.log(logging.INFO, str(e))
                del self.server.clients[self.conn]
                self.conn.close()
                break
            except:
                self.server.log(logging.INFO, traceback.format_exc(limit=None, chain=True))
   
    def get_software_avail(self):
        self.send([ControlCodes["MESSAGE"]] + list("Not yet implemented\0"))
        
    def get_servers(self):
        self.send([ControlCodes["MESSAGE"]] + list("Not yet implemented\0"))
        
    def get_pkg_info(self):
        self.send([ControlCodes["MESSAGE"]] + list("Not yet implemented\0"))
        
    def check_for_updates(self):
        self.send([ControlCodes["MESSAGE"]] + list("Not yet implemented\0"))
        
    def update_packages(self):
        self.send([ControlCodes["MESSAGE"]] + list("Not yet implemented\0"))
                                                
                                                
                                    
        
