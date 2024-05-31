import eventlet
import json
from flask import Flask, render_template ,request,redirect,url_for
from flask_mqtt import Mqtt
from flask_socketio import SocketIO
from flask_bootstrap import Bootstrap
from user import *
import socket
from flask import send_file
import pdfkit
import sqlite3
from dbhandler import *
from fpdf import FPDF
import math

from subprocess import Popen
import sys
import time
import datetime
import os

from ToolHandler import *


if os.path.exists("/home/jackfruit/ncs/BootTime.txt"):
	f=open("/home/jackfruit/ncs/BootTime.txt",'r')
	boottime=f.read()
	print("booted:",boottime)
else:
	boottime="2020-04-14 15:03:26"

try:
	cleandata()
except Exception as e:
	print(e)

booted=False
eventlet.monkey_patch()
mqtt_broker_ip=get_ip()
print("IP Address:",mqtt_broker_ip)
mqtt_username=readsetting("mqtt_username")
mqtt_password=readsetting("mqtt_password")
mqtt_topic=readsetting("mqtt_topic")
mqtt_topic_light=readsetting("topic_light")
page_zoom=readsetting("pagezoom")
DB_Name=readsetting("DB_Name")
activeData={}

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MQTT_BROKER_URL'] = mqtt_broker_ip
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_USERNAME'] = mqtt_username
app.config['MQTT_PASSWORD'] = mqtt_password
app.config['MQTT_KEEPALIVE'] = 64800  #5
app.config['MQTT_TLS_ENABLED'] = False
app.config['MQTT_CLIENT_ID'] = 'rpibroker'

mqtt = Mqtt(app)
socketio = SocketIO(app)
BxSwitches,tdev=Switch_IDandCount()
for boxid,clid in BxSwitches.items():
		if boxid not in activeData.keys():
			activeData[boxid]={}
		for client in clid:
			if client not in activeData[boxid].keys():
				activeData[boxid][client]=False
audFiles={}
for i in range(1,tdev+1):
	audFiles[str(i)]="cust_sound/"+str(i)+".mp3"
audFiles[str(tdev+1)]="sound/bell.mp3"
print(BxSwitches)
#mqtt.subscribe(mqtt_topic,1)

mqtt.subscribe(mqtt_topic,1)
mqtt.subscribe('Tool/ToolData')

@app.route('/shutdown')
def shutdown():
	from subprocess import call
	call("sudo shutdown -h now", shell=True)
	return "shutting down now........"

@app.route('/settings',methods=['GET','POST'])
def settings():
	#print('req...args....',request.args.get)
	#print(request.get_data().decode())
	if request.method=="POST":

		ajxdata=json.loads(request.get_data().decode())
		print(ajxdata,type(ajxdata))
		if(ajxdata['dataFrom']=="Zoom"):
			zoomdata=int(ajxdata["value"])/100
			print("PagezoomScale",zoomdata)
			setsetting("pagezoom",str(zoomdata))
			socketio.emit('reload', data="Reload")
		if(ajxdata['dataFrom']=="Time"):
			datetime1=ajxdata["value"]
			date,time=datetime1.split('T') 
			print(date,time)
			datetimedata="\"" +date + " " +time+"\""
			p = Popen("sudo date -s "+datetimedata, shell=True)
			p.wait()
			p = Popen("sudo hwclock -w", shell=True)
			p.wait()
			f=open("/home/jackfruit/ncs/BootTime.txt","w")
			f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
			f.close()
	print("Ajax Call",request.method)
	zoomvalue=int(float(readsetting("pagezoom"))*100) 
	Currentdate=curtime=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")  
	return render_template('settings.html',zoomvalue=str(zoomvalue),datenow=Currentdate)
	

@app.route('/report')
def mpdf():
	duration=readsetting("esc_duration")
	return render_template('report.html',data=retrivedatafromDB(duration))

@app.route('/reboot')
def reboot():
	from subprocess import call
	call("sudo reboot now", shell=True)
	return "restating now........"


@app.route('/devop')
def devop():
	global activeData
	global audFiles
	actualbedcount=int(readsetting("beds"))
	#return str(actualbedcount)
	dsptxt=retrivebednaming()
	BxSwitches,tdev=Switch_IDandCount()
	noofcolumn=int(readsetting("tablecolumn"))
	actualbedcount=int(readsetting("beds"))
	ToiletSwitchs=int(readsetting("Tlight"))
	totalbed=(math.ceil(actualbedcount/noofcolumn))*noofcolumn
	loopvalue=totalbed+1
	dsptxt=retrivebednaming()
	print("DSPTXT:",dsptxt)

	totalaudFiles=actualbedcount+ToiletSwitchs
	

	return BxSwitches

@app.route('/refreshdata')
def refreshdata(): 
	global activeData   
	for boxs in activeData.keys():
		for ids in activeData[boxs].keys():
			activeData[boxs][ids]=False
	return "Successfull"+str(activeData)

@app.route('/clearlogs')
def clearlogs(): 
	clearHistoryTable()
	return "Cleared Logs..!!"

@app.route('/')
def index():
	global activeData
	global booted
	global audFiles
	global tdev
	noofcolumn=int(readsetting("tablecolumn"))
	actualbedcount=int(readsetting("beds"))
	ToiletSwitchs=int(readsetting("Tlight"))
	totalbed=(math.ceil(actualbedcount/noofcolumn))*noofcolumn
	loopvalue=totalbed+1
	dsptxt=retrivebednaming()
	page_zoom=readsetting("pagezoom")
	print("DSPTXT:",dsptxt)

	totalaudFiles=actualbedcount+ToiletSwitchs
	print("BxSwitches---",BxSwitches)
	booted=True
	return render_template('index.html',noofcolumn=noofcolumn,totalbed=totalbed,loopvalue=loopvalue,zommdata=page_zoom,actualbedcount=actualbedcount,dsptxt=dsptxt,audFiles=audFiles,BT_swcount=tdev+1,BxSwitches=BxSwitches)
	




@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
	mqtt.subscribe(mqtt_topic,1)
	mqtt.subscribe('Tool/ToolData')
	


@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
	try:
		global activeData
		global booted
		if booted==False:
			print("NOT YET LOADED!!")
			pass
		topictmp,clienttmp=message.topic.split("/",1)
		print("===>",topictmp,clienttmp)
		if topictmp == 'Tool' and clienttmp == 'ToolData':
			print("Data From Tool")
			jsonData=message.payload.decode()
			info=json.loads(jsonData)
			#print(res)
			print(info['appsetting']['DB_Name'])
			dbfile=info['appsetting']['DB_Name']
			ClearAllTables(dbfile)
			UpdateAllTables(dbfile,info)
			print("Done")  # Check Here
			#time.sleep(5)
			socketio.emit('reload', data="Reload")
			from subprocess import call
			call("sudo reboot now", shell=True)
			return "restating now........"
			


		else:
			getclientid=clienttmp
			modfiedboxdata=retrivebox(clienttmp)
			clienttmp=modfiedboxdata[0][0]
			print("gotdata",modfiedboxdata[0][0])
			print("gotdata",modfiedboxdata[0][1])
			#print("ActiveData:",activeData[clienttmp][clienttmp])
			boxsuffix=modfiedboxdata[0][1][-1]
			if boxsuffix.isnumeric():
				boxsuffix="-"
			data = dict(
				topic=topictmp,
				client=clienttmp,
				boxname=modfiedboxdata[0][1],
				payload=message.payload.decode(),
				clientid=getclientid,
				suffix=boxsuffix
				# client=message.clientid
			)
			


			cid=int(getclientid)
			
			if (data['payload']=="150" or data['payload']=="210" or data ['payload']=="250") and booted==True:
				print("ON")
				activeData[clienttmp][cid]=True
			elif data['payload']=="180" and booted==True:
				print("OFF")
				activeData[clienttmp][cid]=False

			data['Effect']=False
			for clientID in activeData[clienttmp]:
				if activeData[clienttmp][clientID]==True:
					data['Effect']=True
					print("if")
				print("for")
				  
		  
			print (data)
			datadupl=data
			print(clienttmp)
			
			print("publishdata")

			data['booted']=booted
			socketio.emit('mqtt_message', data=data)
			t1=datetime.datetime.strptime(boottime,"%Y-%m-%d %H:%M:%S")
			t2=datetime.datetime.now()
			timediff=abs((t2-t1).total_seconds())  
			if timediff>20:
				Update_For_Analytics(datadupl)
				print("OK")
			else:
				print("TmeDifferance:",timediff)
				print("Skipped")
	except ValueError:
		print("Value Error raised..")
	except Exception as e:
		print(e)




	



@mqtt.on_log()
def handle_logging(client, userdata, level, buf):
	#print("Checking..")
	#print(level, buf)
	pass

if __name__ == '__main__':
	socketio.run(app, host=get_ip(), port=80, use_reloader=False, debug=True) #use_reloader=True
