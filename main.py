import time
from ssd1306 import SSD1306_I2C
from fifo import Fifo
import requests
import network
import math
from piotimer import Piotimer
from machine import UART, Pin, I2C, Timer, ADC
import framebuf
from umqtt.simple import MQTTClient
import ujson


class Encoder:
    def __init__(self, rot_a, rot_b, swp):
        self.a = Pin(rot_a, mode=Pin.IN)
        self.b = Pin(rot_b, mode=Pin.IN)
        self.sw = Pin(swp, mode=Pin.IN, pull=Pin.PULL_UP)
        self.fifo = Fifo(30, typecode='i')
        self.last_rotation_time = time.ticks_ms() 

        # Attach interrupt handlers
        self.a.irq(handler=self.handler, trigger=Pin.IRQ_RISING, hard=True)
        self.sw.irq(handler=self.bhandler, trigger=Pin.IRQ_FALLING, hard=True)

    def bhandler(self, pin):
        current_time = time.ticks_ms()
        if current_time - self.last_rotation_time > 200:
            self.fifo.put(0)  # Put a specific value into the FIFO when the button is pressed
            self.last_rotation_time = current_time  # Update last rotation time

    def handler(self, pin):
        self.fifo.put(-1 if self.b.value() else 1)  

class Menu:
    def __init__(self, led_values, rot, oled):
        self.led_values = led_values
        self.rot = rot
        self.oled = oled
        self.selected_index = 0
        self.options = Options(oled, rot, self)
        self.is_menu_displayed = False
        self.font_size = 2
        
    def display_menu(self):
        self.oled.fill(0)
        for i, value in enumerate(self.led_values): #put frame for selected option
            marker = "[" if i == self.selected_index else ""
            marker2 = "]" if i == self.selected_index else ""
            self.oled.text(marker + value + marker2, 0, i * 8, 1)
        self.oled.show()
        self.is_menu_displayed = True


    def run(self):
        self.display_menu()

        while True:
            if self.rot.fifo.has_data():
                rotation = self.rot.fifo.get()
                if not self.is_menu_displayed:
                    if rotation == 0:
                        self.display_menu()
                else:
                    self.handle_menu(rotation)
                    
    def handle_menu(self, rotation):
        if rotation != 0:
            self.selected_index = (self.selected_index + rotation + len(self.led_values)) % len(self.led_values)
            self.display_menu()
        else:
            self.is_menu_displayed = False
            if self.selected_index == 0:
                self.options.is_monitoring_heartRate = True
                self.options.heartRate()
            elif self.selected_index == 1:
                self.options.basic()
            elif self.selected_index == 2:
                self.options.kubios()
            elif self.selected_index == 3:
                self.options.history()

    def welcome_text(self):
        self.oled.fill(1)
        i = 0
        h = 0
        v = 0
        for i in range(6):
            self.oled.pixel(4+h, 3, 0)
            self.oled.pixel(8+h, 3, 0)
            self.oled.pixel(4+h, 54, 0)
            self.oled.pixel(8+h, 54, 0)
        
            self.oled.line(3+h, 4, 5+h, 4, 0)
            self.oled.line(3+h, 55, 5+h, 55, 0)

            self.oled.line(7+h, 4, 9+h, 4, 0)
            oled.line(7+h, 55, 9+h, 55, 0)

            self.oled.line(2+h, 5, 10+h, 5, 0)
            self.oled.line(2+h, 56, 10+h, 56, 0)

            self.oled.line(3+h, 6, 9+h, 6, 0)
            self.oled.line(3+h, 57, 9+h, 57, 0)

            self.oled.line(4+h, 7, 8+h, 7, 0)
            self.oled.line(4+h, 58, 8+h, 58, 0)

            self.oled.line(5+h, 8, 7+h, 8, 0)
            self.oled.line(5+h, 59, 7+h, 59, 0)

            self.oled.pixel(6+h, 9, 0)
            self.oled.pixel(6+h, 60, 0)
            
            i += 1
            h += 23
    
        for i in range(2):
            self.oled.pixel(4+v, 19, 0)
            self.oled.pixel(8+v, 19, 0)
            self.oled.pixel(4+v, 37, 0)
            self.oled.pixel(8+v, 37, 0)
        
            self.oled.line(3+v, 20, 5+v, 20, 0)
            self.oled.line(3+v, 38, 5+v, 38, 0)

            self.oled.line(7+v, 20, 9+v, 20, 0)
            self.oled.line(7+v, 38, 9+v, 38, 0)

            self.oled.line(2+v, 21, 10+v, 21, 0)
            self.oled.line(2+v, 39, 10+v, 39, 0)

            self.oled.line(3+v, 22, 9+v, 22, 0)
            self.oled.line(3+v, 40, 9+v, 40, 0)

            self.oled.line(4+v, 23, 8+v, 23, 0)
            self.oled.line(4+v, 41, 8+v, 41, 0)

            self.oled.line(5+v, 24, 7+v, 24, 0)
            self.oled.line(5+v, 42, 7+v, 42, 0)

            self.oled.pixel(6+v, 25, 0)
            self.oled.pixel(6+v, 43, 0)
            v += 115

        self.oled.text("Hearbest", 26, 17, 0)
        self.oled.text("Pulse", 34, 27, 0)
        self.oled.text("Oximeter", 26, 37, 0)
        self.oled.show()
        time.sleep_ms(3000)

class Options:
    def __init__(self, oled, rot, menu):
        self.oled = oled
        self.rot = rot
        self.menu = menu
        
    def heartRate(self):
        ia = Heart_adc("GP27", self.oled)
        tmr = Piotimer(mode=Piotimer.PERIODIC, freq=250, callback=ia.handler)
        while True:
            ia.run()
            if not rot.fifo.empty() and rot.fifo.get() == 0:
                break
        self.menu.display_menu()
    
    def basic(self):
        ia = Heart_adc("GP27", self.oled)
        tmr = Piotimer(mode=Piotimer.PERIODIC, freq=250, callback=ia.handler)
        start_time = time.ticks_ms()
        while True:
            ia.run()
            elapsed_time = time.ticks_diff(time.ticks_ms(), start_time)
            if elapsed_time >= 30000: #Take data in 30 seconds then analyze
                analysis = HR_analysis(ia.saved_PPIs, ia.saved_hr)
                mean_ppi = analysis.meanPPI()
                mean_hr = analysis.average_heartRate()
                sdnn = analysis.SDNN()
                rmssd = analysis.RMSSD()
                #Draw on OLED
                self.oled.fill(0)
                self.oled.text('Your HR analysis:', 0, 0)
                self.oled.text('mean PPI: '+str(mean_ppi), 0, 15)
                self.oled.text('mean HR: '+str(mean_hr)+' bpm', 0, 27)
                self.oled.text('SDNN: '+str(sdnn), 0, 39)
                self.oled.text('RMSSD: '+str(rmssd), 0, 51)
                self.oled.show()
                #Send data via MQTT
                data_sender = DataSender("KME661_group2", "12345678", "192.168.2.253")    
                # Connect to WLAN
                data_sender.connect_wlan()                
                # Connect to MQTT
                data_sender.connect_mqtt()                           
                # Create measurement dictionary
                measurement = {
                    "mean_hr": mean_hr,
                    "mean_ppi": mean_ppi,
                    "rmssd": rmssd,
                    "sdnn": sdnn,
                }
                
                # Send measurement data over MQTT
                data_sender.send_measurement_data("Group2", measurement)
                break
                
    
    def kubios(self):
        ia = Heart_adc("GP27", self.oled)
        tmr = Piotimer(mode=Piotimer.PERIODIC, freq=250, callback=ia.handler)
        start_time = time.ticks_ms()
        while True:
            ia.run()
            elapsed_time = time.ticks_diff(time.ticks_ms(), start_time)
            if elapsed_time >= 30000: #Take data in 30 seconds then analyze
                PPIs = ia.saved_PPIs
                try:
                    wlan = network.WLAN(network.STA_IF)
                    wlan.active(True)
                    wlan.connect("KME661_group2", "12345678")
                    if wlan.isconnected():
                        APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a" 
                        CLIENT_ID = "3pjgjdmamlj759te85icf0lucv" 
                        CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef" 
                        TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token" 

                        response = requests.post( 
                            url = TOKEN_URL, data = 'grant_type=client_credentials&client_id={}'.format(CLIENT_ID), 
                            headers = {'Content-Type':'application/x-www-form-urlencoded'}, auth = (CLIENT_ID, CLIENT_SECRET)) 
                        response = response.json() #Parse JSON response into a python dictionary
                        access_token = response["access_token"] #Parse access token out of the response dictionary 
                        
                        self.oled.fill(0)
                        self.oled.text('Analyzing...', 0, 5)
                        self.oled.show()

                        data_set = {
                            "type": "RRI",
                            "data": PPIs,
                            "analysis": {
                            "type": "readiness"}
                            }

                        # Make the readiness analysis with the given data 
                        response = requests.post( url = "https://analysis.kubioscloud.com/v2/analytics/analyze", 
                            headers = { "Authorization": "Bearer {}".format(access_token), 
                            #use access token to access your KubiosCloud analysis session 
                            "X-Api-Key": APIKEY }, 
                            json = data_set) #dataset will be automatically converted to JSON by the urequests library 
                        response = response.json() 
                        #Print out the SNS and PNS values on the OLED screen
                        time_stamp = response['analysis']['create_timestamp']
                        print(time_stamp)
                        meanRR = int(response['analysis']['mean_rr_ms'])
                        meanHR = int(response['analysis']['mean_hr_bpm'])
                        sdnn = int(response['analysis']['sdnn_ms'])
                        rmssd = int(response['analysis']['rmssd_ms'])
                        
                        try:
                            history_file = open("Kubios_history.txt", "w")
                            history_file.write("Time: " + str(time_stamp)+ "\n" 
                                                + "Mean RR: " + str(meanRR) + "\n" 
                                                + "Mean HR: " + str(meanHR)+ "\n" 
                                                + "SDNN: " + str(sdnn)+ "\n" 
                                                + "RMSSD: " + str(rmssd))
                            history_file.close()  # Close the file after writing
                            print("File 'Kubios_history.txt' created successfully.")
                        except Exception as e:
                            print("Error creating file:", e)
                            
                        self.oled.fill(0)
                        self.oled.text('Kubios says: ',10,0)
                        self.oled.text('mean PPI: '+ str(meanRR) ,0, 15)
                        self.oled.text('mean HR: '+str(meanHR)+' bpm',0, 27)
                        self.oled.text('SDNN: '+str(sdnn),0, 39)
                        self.oled.text('RMSSD: '+str(rmssd),0, 51)
                        self.oled.show()
                    else:
                        print("Failed to connect to WiFi.")
                except Exception as e:
                    print("Error:", e)
                break

    def history(self):
        self.oled.fill(0)
        try:
            # Open the file and read all lines
            with open('Kubios_history.txt', 'r') as file:
                lines = file.readlines()

            # Extract line and its content
            line_and_content = [line.strip().split(': ') for line in lines]

            # Initialize variables to store extracted values
            meanRR = None
            meanHR = None
            sdnn = None
            rmssd = None

            # Iterate over extracted lines and content
            for line, content in line_and_content:
                if line == 'Mean RR':
                    meanRR = content
                elif line == 'Mean HR':
                    meanHR = content
                elif line == 'SDNN':
                    sdnn = content
                elif line == 'RMSSD':
                    rmssd = content

            # Display on OLED
            self.oled.fill(0)
            self.oled.text("Time:" + line_and_content[0][1], 8, 0)
            self.oled.text('mean PPI: ' + str(meanRR), 0, 15)
            self.oled.text('mean HR: ' + str(meanHR) + ' bpm', 0, 27)
            self.oled.text('SDNN: ' + str(sdnn), 0, 39)
            self.oled.text('RMSSD: ' + str(rmssd), 0, 51)
            self.oled.show()
        except Exception as e:
            print("Error: ", e)
            
class Heart_adc:    
    def __init__(self, adc_pin_nr, oled):
        self.av = ADC(adc_pin_nr)  # Sensor AD channel
        self.fifo = Fifo(500)     # FIFO where ISR will put samples
        self.avg_list = []
        self.threshold_percentage = 0.8
        self.index = 0
        self.min_hr = 40
        self.max_hr = 200
        self.peak_found = False
        self.first_peak_found = False
        self.prev_sample = 0        
        self.filtered_AD = 0
        self.threshold = 0
        self.hr = 0
        self.prev_sample = 0
        self.hr_values = [] # to calculate average of 5 HR values
        self.average_hr = 0
        
        # data below is for HR_analysis.py
        self.saved_hr = [] # save average HR values for later analysis
        self.saved_PPIs = [] #save PPIs values for later analysis
        
        self.oled = oled
        self.new_time = time.ticks_ms()
        self.old_time = self.new_time
        self.prev_x = -1
        self.prev_y = 45
                     
    def handler(self, tid):
        ad = self.av.read_u16()
        self.fifo.put(ad)

    def filter_raw_AD(self):
        raw_AD = self.fifo.get()
        self.avg_list.append(raw_AD)
        
        if len(self.avg_list) > 5:
            self.avg_list.pop(0)    
            self.filtered_AD = sum(self.avg_list)/len(self.avg_list)
        
    def find_threshold(self):
        #calculating threshold
        max_value = max(self.fifo.data)
        min_value = min(self.fifo.data)
        amplitude = max_value - min_value
        self.threshold = min_value + self.threshold_percentage * amplitude
        return self.threshold #this line may not be necessary
        
    def calculate_bpm(self):
        ppi_samples = self.index - 1 #| calculate ppi in number of samples
        ppi_ms = ppi_samples * 4 # 1 sample 4 ms
        self.saved_PPIs.append(ppi_ms)
        heart_rate =round(60000 / ppi_ms) # calculate heart rate in BPM
        if heart_rate >= self.min_hr and heart_rate <= self.max_hr: # checking if HR is within the range make check also 1
            self.hr = heart_rate
            self.hr_values.append(self.hr) #add to list to calculate mean of 5 HRs
            self.find_averageHR()
        
    def find_peak(self):
        self.filter_raw_AD()
        current = self.filtered_AD
        threshold = self.find_threshold()
        if current > threshold:
            if self.prev_sample > current:
                if not self.peak_found:
                    if self.first_peak_found:
                        self.calculate_bpm()
                else:    
                    self.first_peak_found = True
                self.peak_found = True
                self.index = -1 #reset index to calculate next PPI
        else:
            self.peak_found = False
        self.prev_sample = current        
        self.index += 1 
        
    def find_averageHR(self):
        if self.hr != 0: #avoid adding default value 0            
            if len(self.hr_values) > 5: #calculate average of 5 latest HRs
                self.hr_values.pop(0)
                self.average_hr = round(sum(self.hr_values) / len(self.hr_values))#calculate average of 5 HRs
                print("Heart rate:", self.average_hr, "bpm")
                self.saved_hr.append(self.average_hr)
                
    def draw_OLED(self):
        #Update upper part of the OLED
        self.oled.fill_rect(0, 0, 128, 32, 0)
        self.oled.text("Measuring HR...", 0, 5, 1)
        self.oled.text(str(self.average_hr), 30, 20, 1)
        self.oled.text("bpm", 60, 20, 1)
        #Update lower part of the OLED 
        y = 20 + self.oled.height - int(self.filtered_AD * self.oled.height / 65535)
        y = max(33, min(63,y))
        x = self.prev_x + 1 # 
        print(y)
        self.oled.line(self.prev_x, self.prev_y, x, y, 1)
        self.oled.show()        
        self.prev_x = x
        self.prev_y = y
        if self.prev_x > self.oled.width: #check if line reach right edge
            self.oled.fill(0) 
            self.prev_x = 0  

    def run(self):
        if not self.fifo.empty():
            self.find_peak()
            self.new_time = time.ticks_ms()
            
            if self.new_time - self.old_time > 500:
                self.old_time = time.ticks_ms()
                self.draw_OLED()
class HR_analysis:
    def __init__(self, PPIs, HRs): # Note: PPIs must be in ms
        self.PPIs = PPIs
        self.HRs = HRs
    
    def meanPPI(self):
        meanppi = sum(self.PPIs) / len(self.PPIs)
        return meanppi
    
    def average_heartRate(self): #parameter: list of HRs
        average_heartRate = round(sum(self.HRs) / len(self.HRs))
        return average_heartRate

    
    def SDNN(self):
        mean_ppi = self.meanPPI()  
        sdnn_value = (sum((x - mean_ppi) ** 2 for x in self.PPIs) / len(self.PPIs)) ** 0.5
        return sdnn_value

    
    def RMSSD(self): 
        successive_diffs = [self.PPIs[i + 1] - self.PPIs[i] for i in range(len(self.PPIs) - 1)]
        squared_diffs = [x ** 2 for x in successive_diffs]
        mean_squared_diffs = sum(squared_diffs) / len(squared_diffs)
        rmssd_value = mean_squared_diffs ** 0.5
        return rmssd_value
    
class DataSender:
    def __init__(self, ssid, password, broker_ip):
        self.SSID = ssid
        self.PASSWORD = password
        self.BROKER_IP = broker_ip
        self.mqtt_client = None

    # Function to connect to WLAN
    def connect_wlan(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.SSID, self.PASSWORD)
        while not wlan.isconnected():
            print("Connecting... ")
        print("Connection successful. Pico IP:", wlan.ifconfig()[0])

    # Function to connect to MQTT
    def connect_mqtt(self):
        try:
            mqtt_client = MQTTClient("", self.BROKER_IP)
            mqtt_client.connect(clean_session=True)
            self.mqtt_client = mqtt_client
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")

    # Function to send measurement data over MQTT
    def send_measurement_data(self, topic, measurement):
        if self.mqtt_client is None:
            print("MQTT client is not connected.")
            return
        
        json_message = ujson.dumps(measurement)
        try:
            self.mqtt_client.publish(topic, json_message)
            print(f"Sending to MQTT: {topic} -> {json_message}")
        except Exception as e:
            print(f"Failed to send MQTT message: {e}")

i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

rot = Encoder(10, 11, 12)
sw0 = Pin(9, Pin.IN, Pin.PULL_UP)
led_values = ["Measure HR", "BasicHRV", "Kubios", "History"]
menu = Menu(led_values, rot, oled)

menu.welcome_text()
menu.run()





