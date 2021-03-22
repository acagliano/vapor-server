import socket,threading,ctypes,hashlib,json,os,sys,time,math,traceback,logging,gzip,zlib,sympy,random
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


PORT=51000
BUFFER_SIZE=1024

ControlCodes={
    "FETCH_SOFTWARE_LIST":0x10,
    "FETCH_SERVER_LIST":0x11,
    "FETCH_SOFTWARE_INFO":0x12,
    "SRVC_GET_REQ":0x20,
    "FILE_WRITE_START":0x40,
    "FILE_WRITE_DATA":0x41,
    "FILE_WRITE_END":0x42,
    "FILE_WRITE_SKIP":0x43,
    "FILE_WRITE_NEXT":0x44,
    "FILE_GET_UP_TO_DATE":0x43,
    "LIBRARY_CHECK_CRC":0x50,
    "LIBRARY_UPDATE_ITEM":0x51,
    "WELCOME":0xd0,
    "NEGOTIATE_RSA":0xd1,
    "MESSAGE":0xf0,
    "BRIDGE_ERROR":0xf1,
    "SERVER_ERROR":0xf2,
    "SERVER_SUCCESS":0xf3,
    "PING":0xfc
}

PacketSizes={
    "FETCH_SOFTWARE_LIST":1,
    "FETCH_SERVER_LIST":1,
    "FETCH_SOFTWARE_INFO":None,
    "SRVC_GET_REQ":9,
    "FILE_WRITE_START":30,
    "NEGOTIATE_RSA":256
}

FileTypes={
    "TI_PRGM_TYPE":0x05,
    "TI_PPRGM_TYPE":0x06,
    "TI_APPVAR_TYPE":0x15
}

ErrorTypes={
	"SERVER_IO_ERR":0x00,
	"INVALID_PACKET_TYPE":0xfe,
	"SERVER_MISC_EXC":0xff
}

def PaddedString(s, amt, char=" "):
	if len(s)>=amt:
		return s[:amt]
	else:
		return s.ljust(amt, char)

def u32(*args):
    o=[]
    for arg in args:
        if int(arg)<0: arg = abs(int(arg))
        else: arg = int(arg)
        o.extend(list(int(arg).to_bytes(4,'little')))
    return o

def u16(*args):
	o=[]
	for arg in args:
		if int(arg)<0: arg = abs(int(arg))
		else: arg = int(arg)
		o.extend(list(int(arg).to_bytes(2,'little')))
	return o

def u24(*args):
    o=[]
    for arg in args:
        if int(arg)<0: arg = abs(int(arg))
        else: arg = int(arg)
        o.extend(list(int(arg).to_bytes(3,'little')))
    return o
 
def i24(*args):
    o=[]
    for arg in args:
        if int(arg)>0:
            o.extend(list(int(arg).to_bytes(3,'little')))
        else:
            o.extend(list((0-abs(int(arg))&0x7FFFFF).to_bytes(3,'little')))
    return o
    
    
class TI_RSA:
    def gcd(self, a, b):
        while b != 0:
            a, b = b, a % b
            return a
        
    def multiplicative_inverse(self, e, phi):
        d = 0
        x1 = 0
        x2 = 1
        y1 = 1
        temp_phi = phi
        while e > 0:
            temp1 = temp_phi/e
            temp2 = temp_phi - temp1 * e
            temp_phi = e
            e = temp2
        
            x = x2- temp1* x1
            y = d - temp1 * y1
        
            x2 = x1
            x1 = x
            d = y1
            y1 = y
    
        if temp_phi == 1:
            return d + phi

    def generate_keypair(self, p, q):
        p = sympy.randprime(0, 2^64)
        q = sympy.randprime(0, 2^64)

        n = p * q   # P * Q
        phi = (p-1) * (q-1)     # Totient

        #Choose an integer e such that e and phi(n) are coprime
        e = random.randrange(1, phi)

        #Use Euclid's Algorithm to verify that e and phi(n) are comprime
        g = gcd(e, phi)
        while g != 1:
            e = random.randrange(1, phi)
            g = gcd(e, phi)

        #Use Extended Euclid's Algorithm to generate the private key
        d = multiplicative_inverse(e, phi)
    
        #Return public and private keypair
        #Public key is (e, n) and private key is (d, n)
        return ((e, n), (d, n))
        
    def decrypt(self, cipher, pubkey):
        #Unpack the key into its components
        key, n = pubkey
        #Generate the plaintext based on the ciphertext and key using a^b mod m
        plain = [(ord(char) ** key) % n for char in cipher]
        #Return the array of bytes as a string
        return plain
        
    def encrypt(self, pk, data, privkey):
        #Unpack the key into it's components
        key, n = privkey
        #Convert each letter in the plaintext to numbers based on the character using a^b mod m
        cipher = [(ord(char) ** key) % n for char in data]
        #Return the array of bytes
        return cipher
        

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
            self.emit_log(traceback.format_exc(limit=None, chain=True))
            
            
        
    def main(self):
        self.emit_log(logging.INFO, f"server up and runnning on port {self.port}")
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
        while self.online:
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
                    self.emit_log(logging.INFO, "server shutting down in 10s")
                    time.sleep(10)
                    raise ServerExit()
            except (KeyboardInterrupt, ServerExit):
                self.emit_log(logging.INFO, "The server was stopped from Console")
                self.online=False
                break
            except:
                self.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
                pass
            
        
        
class Client:
    def __init__(self, conn, addr, server):
        try:
            self.rsa_enable = False
            self.conn=conn
            self.addr=addr
            self.ip=addr[0]
            self.server=server
            self.send([ControlCodes["WELCOME"]])
        except: self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))

        
    def send(self, data):
        packet_length = len(data)
        i = 0
        self.server.emit_log(logging.DEBUG, f"sending {packet_length}-length packet: {data[:50]}")
        if self.rsa_enable:
            data = TI_RSA.encrypt(data, self.privkey)
        try:
            while packet_length:
                bytes_sent = self.conn.send(bytes(data[i:min(packet_length, BUFFER_SIZE)]))
                if not bytes_sent:
                    raise Exception("packet transmission error")
                    break
                i+=bytes_sent
                packet_length-=bytes_sent
        except: self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
        
    def invalid_packet(self):
        self.server.emit_log(logging.INFO, f"invalid packet sent by {self.ip}")
          
    def handle_connection(self):
        while self.server.online:
            try:
                data = list(self.conn.recv(BUFFER_SIZE))
                if not data:
                    raise ClientDisconnectErr(f"{self.ip} disconnected!")
                
                if self.rsa_enable:
                    data = TI_RSA.decrypt(data, self.rsa_pubkey)
                
                self.server.emit_log(logging.DEBUG, f"packet recieved: {data}")
                if not len(data):
                    continue
                elif data[0]==ControlCodes["FETCH_SOFTWARE_LIST"]:
                    self.get_software_avail()
                elif data[0]==ControlCodes["FETCH_SERVER_LIST"]:
                    self.get_servers()
                elif data[0]==ControlCodes["FETCH_SOFTWARE_INFO"]:
                    odata=self.get_pkg_info()
                elif data[0]==ControlCodes["SRVC_GET_REQ"]:
                    odata=self.get_required(data[1:])
                elif data[0]==ControlCodes["FILE_WRITE_START"]:
                    odata=self.get_file(data[1:])
		elif data[0]==ControlCodes["FILE_WRITE_NEXT"]:
			odata=self.file_send_continue()
                elif data[0]==ControlCodes["NEGOTIATE_RSA"]:
                    self.negotiate_rsa(data[1:])
                else:
                    self.server.emit_log(logging.INFO, f"unregistered packet type {data[0]}")
			self.send([ControlCodes["SERVER_ERROR"]], ErrorTypes["INVALID_PACKET_TYPE"])
            except ClientDisconnectErr as e:
                self.server.emit_log(logging.INFO, str(e))
                del self.server.clients[self.conn]
                self.conn.close()
                return
            except:
                self.server.emit_log(logging.INFO, traceback.format_exc(limit=None, chain=True))
   
    def parse_string(self, str):
        try:
            return list(bytes(str+'\0', 'UTF-8'))
        except:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
            
            
    def negotiate_rsa(self, key):
        self.rsa_pubkey=(int.from_bytes(key[0:128]), int.from_bytes[128:])
        pub, priv = TI_RSA.generate_keypair()
        self.rsa_privkey=priv
        self.send([ControlCodes["NEGOTIATE_RSA"]] + list(int.to_bytes(pub[0])) + list(int.to_bytes[pub[1]]))
        self.rsa_enable = true
        
   
    def get_software_avail(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
        
    def get_servers(self):
        odata=[]
        for obj in os.scandir("/home/servers/services/"):
            try:
                if obj.is_dir():
                    srv_name=obj.name
                    srv_name_padded=PaddedString(srv_name, 8, chr(0))
                    odata+=self.parse_string(srv_name_padded)
                with open(f"/home/servers/services/{obj.name}/service.conf") as f:
                    cfg=json.load(f)
                    if "host" in cfg:
                        host=cfg["host"]
                        host_str=host
                    else:
                        host="127.0.0.1"
                        host_str="local"
                    host_str=PaddedString(host_str, 36, chr(0))
                    odata+=self.parse_string(host_str)
                    port=cfg["port"]
                    odata+=u16(port)
                    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    location = (host, port)
                    if temp_socket.connect_ex(location)==0:
                        odata.append(True)
                    else:
                        odata.append(False)
                    temp_socket.close()
            except:
                self.server.emit_log(logging.INFO, traceback.format_exc(limit=None, chain=True))
        self.send([ControlCodes["FETCH_SERVER_LIST"]] + odata)
        
    def get_required(self, service):
        if not len(service)<PacketSizes["SRVC_GET_REQ"]:
            self.invalid_packet()
            return
        try:
            odata=[]
            service=bytes(service[:-1]).decode("utf-8")
            try:
                with open(f"/home/servers/services/{service}/service.conf", "r") as f:
                    cfg=json.load(f)
                    package=cfg["pkg"]
                    for dep in package:
                        odata+=self.parse_string(PaddedString(dep["name"], 8, chr(0)))
                        if dep["type"]=="appv" or dep["type"]=="libs":
                            odata+=[FileTypes["TI_APPVAR_TYPE"]]
                        else:
                            odata+=[FileTypes["TI_PPRGM_TYPE"]]
                        odata.extend([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
                    self.send([ControlCodes["SRVC_GET_REQ"]] + odata)
            except IOError:
                self.server.emit_log(logging.ERROR, "File IO Error")
                self.send([ControlCodes["SERVER_ERROR"]] + self.parse_string("error loading service config"))
        except:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
            self.send([ControlCodes["SERVER_ERROR"]] + self.parse_string("error processing dependencies for {service}"))
        
    def get_file(self, item, defaults=False):
        if not len(item)==PacketSizes["FILE_WRITE_START"]:
            self.invalid_packet()
            return
        print(f"{item}")
        file=str(bytes(item[:9]), 'utf-8').split('\0', maxsplit=1)[0]
        type=item[9]
        sha1 = list(item[10:])
        try:
		if defaults:
			searchpath="/home/servers/software/libs/"
		else:
			searchpath="/home/servers/software/usr/"
		if type==FileTypes["TI_APPVAR_TYPE"]:
			file_wext+=".8xv"
		else: file_wext+=".8xp"
		filepath=f"{searchpath}{file_wext}.bin"
            
            self.server.emit_log(logging.INFO, f"opening file {filename}")
            
            with open(filename, "rb") as f:
                file_content = list(f.read())
                sha1_hosted = list(hashlib.sha1(bytes(file_content)).digest())
                self.server.emit_log(logging.INFO, f"comparing SHA-1 digests...\nDevice: {sha1}\nHosted {sha1_hosted}")
                if sha1_hosted == sha1:
                    self.server.emit_log(logging.INFO, "Match!")
                    self.send([ControlCodes["FILE_WRITE_SKIP"], 1])
                    return
                self.send([ControlCodes["FILE_WRITE_START"]] + u24(len(file_content)))
		self.curr_file_content = file_content
		self.sha1_curr_file = sha1_hosted
		self.loc_in_data = 0
		self.bytes_remain = len(file_content)
		
	def file_send_continue(self)
		if self.bytes_remain==0:
			odata=[]
                	odata += self.parse_string(PaddedString(file, 8, chr(0)))
                	odata += [type]
                	odata += list(self.sha1_curr_file)
                	self.send([ControlCodes["FILE_WRITE_END"]] + odata )
		else:
			bytes_to_send=min(self.bytes_remain, BUFFER_SIZE-1)]
			self.send(self.curr_file_content[self.loc_in_data:bytes_to_send])
			self.loc_in_data+=bytes_to_send
			self.bytes_remain-=bytes_to_send
            
    def check_for_updates(self):
        return [ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented")
        
    def update_packages(self):
        return [ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented")
                                                

if __name__ == '__main__':
	
	server = Vapor()
                                    
        
