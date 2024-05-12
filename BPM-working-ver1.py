from machine import ADC, Pin
from fifo import Fifo
from piotimer import Piotimer
import time
from machine import UART, Pin, I2C, Timer, ADC
from ssd1306 import SSD1306_I2C
import framebuf
from led import Led

measure_HR = True # OPTION 1 : Change to True if you want to measure HR only
analyze_HR = False # OPTION 2 : Change to True if you want to analyse Basic HR measurement

class Heart_adc:    
    def __init__(self, adc_pin_nr):
        self.av = ADC(adc_pin_nr)  # Sensor AD channel
        self.fifo = Fifo(500)     # FIFO where ISR will put samples
        self.ave_fifo = Fifo(5)
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
        
#         self.oled = HeartRateOLED()
        self.new_time = time.ticks_ms()
        self.old_time = self.new_time
        
             
    def handler(self, tid):
        ad = self.av.read_u16()
        self.fifo.put(ad)
        self.ave_fifo.put(ad)

    def filter_raw_AD(self):
        raw_AD = self.fifo.get()
        self.ave_fifo.get()
        self.filtered_AD = sum(self.ave_fifo.data)/self.ave_fifo.size
        
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
                #test time
#                 self.new_time = time.ticks_ms()
#                 if self.new_time - self.old_time > 5000:
#                 self.oled.HR_measure_screen(self.average_hr)
#                     self.old_time = self.new_time
    
    def run(self):
        if not self.fifo.empty():
            self.find_peak()
#             self.draw_OLED()
    
#     def draw_OLED(self):
#         self.new_time = time.ticks_ms()
#         if self.new_time - self.old_time > 5000:
#             self.oled.HR_measure_screen(self.average_hr)
#         self.old_time = self.new_time
            
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

class HeartRateOLED:
    def __init__(self):
        # Initialize I2C for OLED display
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.oled_width = 128
        self.oled_height = 64
        self.oled = SSD1306_I2C(self.oled_width, self.oled_height, self.i2c)        
        
    def HR_measure_screen(self, hr):
        self.oled.fill(0)
        self.oled.text("Measuring HR...", 0, 10, 1)
        self.oled.text(str(hr), 40, 33, 1)
        self.oled.text("bpm", 70, 33, 1)
        self.oled.show()
        
    def HR_analysis_display(self, meanPPI, meanHR, sdnn, rmssd_value):    
        self.oled.fill(0)
        self.oled.text('Pi Pico says:', 10, 0)
        self.oled.text('mean PPI: '+str(meanPPI), 0, 15)
        self.oled.text('mean HR: '+str(meanHR)+' bpm', 0, 27)
        self.oled.text('SDNN: '+str(sdnn), 0, 39)
        self.oled.text('RMSSD: '+str(rmssd_value), 0, 51)
        self.oled.show() 

ia = Heart_adc("GP27")
tmr = Piotimer(mode=Piotimer.PERIODIC, freq=250, callback=ia.handler)
start_time = time.ticks_ms()

import network
from time import sleep
from umqtt.simple import MQTTClient
import ujson

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
            sleep(1)
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

while True:
    if measure_HR: # OPTION 1: MEASURE HEART RATE
        ia.run()        
    
    if analyze_HR: # OPTION 2: ANALYZE HEART RATE (MEAN HR, PPI, SDNN, RMSSD)
        ia.run()
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time)
        if elapsed_time >= 15000: #Take data in 15 seconds then analyze
            analysis = HR_analysis(ia.saved_PPIs, ia.saved_hr)
            mean_ppi = analysis.meanPPI()
            mean_hr = analysis.average_heartRate()
            sdnn = analysis.SDNN()
            rmssd = analysis.RMSSD()
            print("Mean PPI:",mean_ppi)
            print("Mean HR:",mean_hr)
            print("SNDD:",sdnn)
            print("RMSSD:",rmssd)
#             ia.oled.HR_analysis_display(mean_ppi, mean_hr, sdnn, rmssd) #  fixed by adding self for HR def

#             data_sender = DataSender("SmartIotMQTT", "SmartIot", "192.168.1.254")
# 
#             # Connect to WLAN
#             data_sender.connect_wlan()
#             
#             # Connect to MQTT
#             data_sender.connect_mqtt()
#             
#             
#             # Create measurement dictionary
#             measurement = {
#                 "mean_hr": mean_hr,
#                 "mean_ppi": mean_ppi,
#                 "rmssd": rmssd,
#                 "sdnn": sdnn,
#             }
#             
#             # Send measurement data over MQTT
#             data_sender.send_measurement_data("Group2", measurement)
#             break

                   
