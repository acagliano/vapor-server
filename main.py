import socket,threading,ctypes,hashlib,json,os,sys,time,math,traceback,logging,gzip,zlib
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


PORT=51000
BUFFER_SIZE=1024

ControlCodes={
    "FETCH_SOFTWARE_LIST":0x10,
    "FETCH_SERVER_LIST":0x11,
    "FETCH_SOFTWARE_INFO":0x12,
    "SRVC_GET_REQ":0x20,
    "SRVC_REQ_INFO":0x21,
    "FILE_WRITE_START":0x40,
    "FILE_WRITE_DATA":0x41,
    "FILE_WRITE_END":0x42,
    "FILE_WRITE_SKIP":0x43,
    "FILE_GET_UP_TO_DATE":0x43,
    "LIBRARY_CHECK_CRC":0x50,
    "LIBRARY_UPDATE_ITEM":0x51,
    "WELCOME":0xd0,
    "MESSAGE":0xf0,
    "BRIDGE_ERROR":0xf1,
    "SERVER_ERROR":0xf2,
    "SERVER_SUCCESS":0xf3,
    "PING":0xfc
}

FileTypes={
    "TI_PRGM_TYPE":0x05,
    "TI_PPRGM_TYPE":0x06,
    "TI_APPVAR_TYPE":0x15
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
                self.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
                pass
            
        
        
class Client:
    def __init__(self, conn, addr, server):
        try:
            self.conn=conn
            self.addr=addr
            self.ip=addr[0]
            self.server=server
            self.send([ControlCodes["WELCOME"]])
        except: self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))

        
    def send(self, data):
        packet_length = len(data)
        i = 0
        self.server.emit_log(logging.DEBUG, f"sending {packet_length}-length packet: {data[:5]}")
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
                elif data[0]==ControlCodes["UPDATE_SOFTWARE"]:
                    odata=self.update_packages()
                else:
                    self.server.emit_log("Bad Packet Id")
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
   
    def get_software_avail(self):
        self.send([ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented"))
        
    def get_servers(self):
        odata=[]
        for obj in os.scandir("/home/servers/services/"):
            try:
                if obj.is_dir():
                    srv_name=obj.name
                    print(srv_name)
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
                        odata.extend([0,0,0,0,0,0,0,0,0])
                    self.send([ControlCodes["SRVC_REQ_INFO"]] + odata)
            except IOError:
                self.server.emit_log(logging.ERROR, "File IO Error")
                self.send([ControlCodes["SERVER_ERROR"]] + self.parse_string("error loading service config"))
        except:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
            self.send([ControlCodes["SERVER_ERROR"]] + self.parse_string("error processing dependencies for {service}"))
        
    def get_file(self, item):
        print(f"{item}")
        file=str(bytes(item[:9]), 'utf-8').split('\0', maxsplit=1)[0]
        type=item[9]
        size = int.from_bytes(item[10:13], 'little')
        device_year = int.from_bytes(item[13:16], 'little')
        device_month = item[17]
        device_day = item[18]
        archive = True if (type==FileTypes["TI_APPVAR_TYPE"]) else False
        try:
            if type==FileTypes["TI_APPVAR_TYPE"]:
                if os.path.isfile(f"/home/servers/software/libs/{file}.bin"):
                    filename=f"/home/servers/software/libs/{file}.bin"
                elif os.path.isfile(f"/home/servers/software/appv/{file}.bin"):
                    filename=f"/home/servers/software/appv/{file}.bin"
                else:
                    self.send([ControlCodes["FILE_WRITE_SKIP"], 5])
                    return
            elif os.path.isfile(f"/home/servers/software/prgm/{file}.bin"):
                filename=f"/home/servers/software/prgm/{file}.bin"
            else:
                self.send([ControlCodes["FILE_WRITE_SKIP"], 5])
                return
            
            self.server.emit_log(logging.INFO, f"opening file {filename}")
            mtime = datetime.fromtimestamp(os.path.getmtime(filename))
            m_year = int(mtime.strftime("%Y"))
            m_month = int(mtime.strftime("%m"))
            m_day = int(mtime.strftime("%d"))
            
            device_days = device_day + (30 * device_month) + (30 * 12 * device_year)
            file_days = m_day + (30 * m_month) + (30 * 12 * m_year)
            if(device_days >= file_days):
                self.send([ControlCodes["FILE_WRITE_SKIP"], 1])
                self.server.emit_log(logging.INFO, f"device timestamp matches {file}. skipping")
                return
            
            print(mtime)
            with open(filename, "rb") as f:
                file_content = list(f.read())
                self.send([ControlCodes["FILE_WRITE_START"]] + u24(len(file_content)))
                for r in range(0, len(file_content), BUFFER_SIZE-1):
                    block=file_content[r:r+BUFFER_SIZE-1]
                    self.send([ControlCodes["FILE_WRITE_DATA"]] + block)
                odata=[]
                
                odata += self.parse_string(PaddedString(file, 8, chr(0)))
                odata += [type]
                odata += u24(m_year) + [m_month, m_day, archive]
                self.send([ControlCodes["FILE_WRITE_END"]] + odata )
        except IOError:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
        except:
            self.server.emit_log(logging.ERROR, traceback.format_exc(limit=None, chain=True))
            
    def check_for_updates(self):
        return [ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented")
        
    def update_packages(self):
        return [ControlCodes["MESSAGE"]] + self.parse_string("Not yet implemented")
                                                

if __name__ == '__main__':
	
	server = Vapor()
                                    
        
