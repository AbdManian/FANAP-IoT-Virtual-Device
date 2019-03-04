import paho.mqtt.client as mqtt
import json
from threading import Thread
import time
import base64
import logging



logger = logging.getLogger(__name__)


C_ATTRIBUTE = 'attributeTypes'

QM_SCAPE = '@$?@$'


class Vdev:
    DATA_FIELD = 'data'

    def __init__(self, platform_file, dev_file,
        enable_subscribe=True,
        device_id = None,
        enc_key = None,
        on_connect_tx_message="",
        loop=False):

        self.device_stopped = False
        self.enable_subscribe = enable_subscribe 

        self.device_id = device_id
        self.enc_key = enc_key
        self.loop = loop
        self.enc_en = False


        self.process_config_files(platform_file, dev_file)
        self.on_connect_tx_message = on_connect_tx_message
        self.tx_done = False
        self.update_function=None


        if self.enc_en:
            import pyDes
            key = (self.enc_key + '0'*8)[:8]
            self.des = pyDes.des(key, pyDes.ECB, padmode=pyDes.PAD_PKCS5)

    def process_config_files(self, platform_file, dev_file):

        with open(dev_file, 'r') as f:
            dev_dic = json.load(f)

        with open(platform_file, 'r') as f:
            self.plat_dic = json.load(f)

        if self._validate_device_json(dev_dic):
            device_type_list = self.get_typelist(dev_dic)
        else:
            self.stop()
            return

        if not self.device_id:
            self.device_id = dev_dic['device_id']
        

        if not self.enc_key:
            self.enc_key = dev_dic['enc_key']
        
        self.enc_en = dev_dic.get('enc_enable', False)

        # if self.enc_key:
        #     self.enc_en = True
        # elif self.dev_dic.get('enc_enable', False):
        #     self.enc_en = True
        #     self.enc_key = self.dev_dic['enc_key']

        
        # Create device type/data list
        self.create_device_type_data_dict(device_type_list)

    def create_device_type_data_dict(self, device_type_list):
        type_dic, data_dic = {}, {}
        for type_field in device_type_list:
            name, data_type = type_field['name'], type_field['type']

            type_str = data_type
            items = []

            if isinstance(data_type, list):
                type_str = 'Enum'
                items = data_type
            else:
                type_str = data_type
                items = ['WHAT?']

            type_dic[name] = {'type':type_str, 'items':items}

            default_values = {'Boolean':False, 'String':'-', 'Enum':items[0], 'Number':0}

            data_dic[name] = default_values[type_str]

            self.device_type_dic = type_dic
            self.device_data_dic = data_dic
            self.device_attribute_type_list = device_type_list

    def get_typelist(self, dev_dic):
        return dev_dic[C_ATTRIBUTE]
      
    def _validate_device_json(self, jdic):
        field = C_ATTRIBUTE 
        error_message = 'Error in device json file'
        if not field in jdic:
            self.error_report('{}. "{}" is not defined'.format(error_message, field))
            return False

        type_dic = jdic[field]

        if not isinstance(type_dic, list):
            self.error_report('{}. {} should be a list'.format(error_message, field))
            return False
        
        for type_def in jdic[field]:
            if (not isinstance(type_def, dict) or 
            not 'name' in type_def or
            not 'type' in type_def or
            not isinstance(type_def['name'], str) or
            not isinstance(type_def['type'], (str,list))):
               
               self.error_report('{}. Invalid type definition "{}"'.format(error_message, type_def))
               return False
            
            if isinstance(type_def['type'], list):
                # Enum type. Check all types should be string
                if len(type_def['type'])==0:
                    self.error_report('{}. Enum list is empty'.format(error_message))
                    return False                    

                for x in type_def['type']:
                    if not isinstance(x, str):
                        self.error_report('{}. Invalid enum value'.format(error_message))
                        return False
            
            
        return True

    def error_report(self, message):
        logger.error(message)    

    def stop(self):
        self.device_stopped = True
    
    def is_stopped(self):
        return self.device_stopped

    def connect(self):
        self.setup_mqtt()

    def setup_mqtt(self):
        self.client = mqtt.Client()

        self.client.on_connect = self.mqtt_on_connect
        self.client.on_message = self.mqtt_on_message
        self.client.on_publish = self.mqtt_on_publish

        mqtt_info = self.plat_dic['mqtt']

        user, password = mqtt_info['user'], mqtt_info['pass']

        u_str = ""
        if user:
            self.client.username_pw_set(user, password)
            u_str = "User:{} Pass:{}".format(user, password)

        host, port = mqtt_info['host'], mqtt_info['port']
        self.client.connect(host, port, 60)

        logger.info("Connect to {}:{} {}".format(host,port,u_str))

        self.client.loop_start()

    def mqtt_on_publish(self, client, userdata, mid):
        self.tx_done = True

    def mqtt_on_connect(self, client, userdata, flags, rc):
        if self.enable_subscribe:
            topic = self.get_p2d_topic()
            client.subscribe(topic)
            logger.info("Subscribe to " + topic)
        else:
            # Here we send message to the platform. Consider command line message
            # as a json request from platform

            logger.info("Subscribe is disabled. Send message to the platform")
            self.process_platform_message("", self.on_connect_tx_message)

    def mqtt_on_message(self, client, userdata, msg):

        payload = msg.payload
        if self.is_enc_en():
            payload = self._dec(msg.payload)
        
        self.process_platform_message(msg.topic, payload)

    def get_p2d_topic(self):
        return '/{}/{}'.format(self.device_id, ('p2d' if not self.loop else 'd2p'))

    def get_d2p_topic(self):
        return '/{}/{}'.format(self.device_id, ('d2p' if not self.loop else 'p2d'))

    def decode_platform_message(self, message):

        try:
            msg = message
            # Message from MQTT is in byte-array format
            if not isinstance(message, str):
                msg = message.decode('utf-8')
            
            msg_data = json.loads(msg)
        except Exception as e:
            self.error_report('Invalid message from platform {} {}'.format(message,e))
            return ""

        
        if not Vdev.DATA_FIELD in msg_data:
            self.error_report('"{}" is missing in platform message {}'.format(Vdev.DATA_FIELD, msg_data))
            return ""
        
        data_list = msg_data[Vdev.DATA_FIELD]

        if not isinstance(data_list, list):
            data_list = [data_list]
            # self.error_report('"DATA" field should be list {}'.format(data_list))
            # return ""
        
        # All entries in data_list should be dict
        for x in data_list:
            if not isinstance(x, dict):
                self.error_report('Invalid field in "{}}" {}'.format(Vdev.DATA_FIELD, data_list))
                return ""
        
            # Check if all fields are defined in device type dict
            for name, value in x.items():
                if not name in self.device_type_dic:
                    self.error_report('Type "{}" is not defined'.format(name))
                    return ""
                

                if value == "?":
                    # This is read-request, don't check the type
                    continue

                type_str = self.device_type_dic[name]['type']
                items = self.device_type_dic[name]['items']


                if type_str=='Boolean' and not isinstance(value, bool):
                    self.error_report('Expect boolean for "{}" < "{}"'.format(name, value))
                    return ""
                
                if type_str=='String' and not isinstance(value, str):
                    self.error_report('Expect string for "{}" < "{}"'.format(name, value))
                    return ""

                if type_str=='Number' and not isinstance(value, (int, float)):
                    self.error_report('Expect number for "{}" < "{}"'.format(name, value))
                    return ""
                
                if type_str=='Enum' and not value in items:
                    self.error_report('Invalid value for enum "{}" "{}" < "{}"'.format(name, items, value))
                    return ""
        
        return data_list

    def process_platform_message(self, topic, payload):
        platform_data = self.decode_platform_message(payload)

        if platform_data:
            read_request = self.apply_data_from_platform(platform_data)
            if not self.loop:
                self.apply_read_request(read_request)
    
    def apply_data_from_platform(self, data_list):
        read_request = set()
        for data in data_list:
            for name, value in data.items():
                
                if value != '?':
                    if value == QM_SCAPE:
                        value = '?'
                    self.update_device_data(name, value)

                read_request.add(name)
                
        if self.update_function:
            self.update_function(self.device_data_dic)

        return read_request

    def update_device_data(self, name, value):
        logger.info('Write "{}"->"{}"'.format(name, value))
        self.device_data_dic[name] = value

    def update_by_name_value_dict(self, update_dic):
        read_req=[]
        for name, value in update_dic.items():
            self.update_device_data(name, value)
            read_req.append(name)
        self.apply_read_request(read_req)

    def apply_read_request(self, read_request=None):

        if read_request==None:
            data_to_send = self.device_data_dic
        else:
            data_to_send = dict([
                (name, self.device_data_dic[name]) for name in read_request
                ])

        data_dic = self._create_response_dict([data_to_send])

        self._push_dict_to_platform(data_dic)

    def _create_response_dict(self, data_list):
        data = data_list
        #if self.loop:
        #    data = data_list[0]

        return {Vdev.DATA_FIELD:data}

    def _push_dict_to_platform(self, data_dic):
        
        jdata = json.dumps(data_dic)
        
        logger.debug('Send message to platform msg={}'.format(jdata))
        
        if self.is_enc_en():
            jdata = self._enc(jdata)

        return self.client.publish(self.get_d2p_topic(), jdata)

    def get_deviceid(self):
        return self.device_id

    def get_data_dict(self):
        return self.device_data_dic

    def _enc(self, msg):
        d = self.des.encrypt(msg)
        x = base64.b64encode(d)
        return x

    def _dec(self, msg):
        x = base64.b64decode(msg)
        return self.des.decrypt(x)

    def is_enc_en(self):
        return self.enc_en

    def set_update_function(self, func):
        self.update_function=func

    def get_logger(self):
        return logger
    
    def send_to_platform_from_queue(self, queue):
        while True:
            qdata = queue.get()
            data_dic = self._create_response_dict([qdata])
            self._push_dict_to_platform(data_dic)
