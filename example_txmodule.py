# Example data generation.
#
# Each stream is determined in form of 
#   def gen_NAME(dev_type_dic, user_data):
#         yield (DATA_DIC, DELAY_TIME_IN_SEC)
#

import random


def gen_field_bool(dev_type_dic, user_data={}):
    while True:
        yield ({"f_bool":True},  random.normalvariate(2,1))
        yield ({"f_bool":False}, random.normalvariate(2,1))
        

def gen_field_num(dev_type_dic, user_data={}):
    cnt = 0
    while True:
        yield ({"f_num":cnt},  0.2)
        cnt += 1

def gen_field_string(dev_type_dic, user_data={}):
    enum_items = dev_type_dic['f_enum']['items']
    while True:

        for i in range(16):
            yield ({"f_str":">"*i, "f_enum":random.choice(enum_items)},  0.5)

        yield ({"f_str":"<"*16},  0.2)
        yield ({"f_str":">"*16},  0.2)
        yield ({"f_str":"<"*16},  0.2)
        yield ({"f_str":">"*16},  0.2)

        for i in range(15, -1, -1):
            yield ({"f_str":"<"*i, "f_enum":enum_items[-1]},  0.4)
