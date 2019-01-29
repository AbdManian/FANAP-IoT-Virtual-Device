#! /usr/bin/python3
import time
from vdev import Vdev
import argparse
import sys
import logging
import json

logger = logging.getLogger("root")
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(name)s:%(levelname)s:%(message)s')


def convert_arg_to_json_string(arg_str):
    parts = arg_str.split('=', maxsplit=1)
    if len(parts) != 2:
        logger.error('Invalid command format. Use Name=Value.')
        return None
    return '{{"{}":{}}}'.format(*parts)

def convert_tx_param_to_json_command(param_list):
    fields_dic = []
    for param in param_list:
        d = convert_arg_to_json_string(param)
        if d!=None:
            fields_dic.append(d)
    return '{{"DATA":[{}]}}'.format(",".join(fields_dic))

def setup_command_args():
    parser = argparse.ArgumentParser(description='Virtual Device simulator')

    parser.add_argument('-p',
        metavar='platform_file', dest='platform', type=str,
        help="Platform JSON file. Default=plat.json",
        default='plat.json')

    parser.add_argument('-d',
        metavar='device_file', dest='device', type=str,
        help="Device JSON file. Default=device.json",
        default='device.json')

    parser.add_argument('param_value', metavar='param_value', 
        help='Commands for sending to the platform. \
        Format PARAM=VALUE, use PARAM=\\"STRING_VAL\\" or PARAM=\'"STRING_VAL"\' for string values.\
        In MS Windows use PARAM="""STRING_VAL"""',
        nargs='*')

    parser.add_argument('-D', metavar='device-id', dest='device_id', type=str,
        help='Set device-id. Overwrites "device_id" in device json file.')
    
    parser.add_argument('-k', metavar='encryption-key', dest='enc_key', type=str,
        help='Set device encryption-key. Overwrites "enc_key" in device json file.')

    parser.add_argument('-txmodule', help='Simulate sending periodic data from device to platform. Content and period is determined in script-file', 
        metavar='script.py', dest='tx_script', type=str)

    parser.add_argument('-gui', help='Show gui in subscribe mode', action='store_true')

    parser.add_argument('-loop', help='Loop two multiple vdev through MQTT. Looped device acts as a platform', action='store_true')

    args = parser.parse_args()

    if (args.param_value or args.tx_script) and args.gui:
        parser.error('-gui is not supported in tx/publish-only mode!')

    if args.param_value and args.tx_script:
        parser.error('-txmodule is not supported with param=value!')

    return parser.parse_args()

def show_press_ctrlc():
    print("Press CTRL+C to quit")

def wait_for_tx_done(dev, tx_script):

    if tx_script:
        from trafficgen import TrafficGen

        tgen = TrafficGen(tx_script, dev.device_type_dic)
        tgen.start()

        show_press_ctrlc()
        try:
            dev.send_to_platform_from_queue(tgen.get_queue())
        except KeyboardInterrupt:
            tgen.end()
            logger.info('Done!')


    else:
        tx_ok = False
        # Set timeout to 2000msec (200*10ms)
        for _ in range(200):
            if dev.tx_done:
                tx_ok = True
                break
            time.sleep(0.01)

        time.sleep(0.3)
        dev.client.disconnect()

def wait_for_subscribe_mode(dev, gui):

    if gui:
        import vui
        import tkinter

        root = tkinter.Tk()
        app = vui.Vui(root, dev.device_attribute_type_list, dev.get_deviceid(), dev.loop)

        dev_logger = dev.get_logger()

        app_log_handler = app.get_logger()
        app_log_handler.setFormatter(logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
        dev_logger.addHandler(app_log_handler)

        app.set_vdev_update_function(dev.update_by_name_value_dict)

        app.update_with_data_dic(dev.get_data_dict())

        dev.set_update_function(app.update_with_data_dic)
        root.mainloop()
    else:
        show_press_ctrlc()
        try:
            while not dev.is_stopped():
                time.sleep(1)            
        except KeyboardInterrupt:
            logger.info('Done!')
        



def run_vdev(args):
    # TX Mode is when there is a parameter for sending to the platform
    tx_mode = args.param_value or args.tx_script

    enable_subscribe = True
    data_to_send = ""

    if tx_mode:
        enable_subscribe = False

        if args.param_value:
            data_to_send = convert_tx_param_to_json_command(tx_mode)
            if not data_to_send:
                return
    

    dev = Vdev(args.platform , args.device, 
        enable_subscribe=enable_subscribe,
        device_id = args.device_id,
        enc_key = args.enc_key,
        on_connect_tx_message = data_to_send,
        loop = args.loop
    )

    if dev.is_stopped():
        return 


    dev.connect()


    if tx_mode:
        wait_for_tx_done(dev, args.tx_script)
    else:
        wait_for_subscribe_mode(dev, args.gui)
 
    

if __name__ == '__main__':

    args = setup_command_args()
    run_vdev(args)    
