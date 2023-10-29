#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
# ############################################################################
#
# openxr.py
# 27/10/2023 (c) Juan M. Casillas <juanm.casillas@gmail.com>
# https://github.com/juanmcasillas/pyopenxr-toolkit-config
#
# Configures some registry options from command line, so you don't need to start the app, 
# then open the OpenXR-Toolkit and restart the session.
#
# usage: openxr.py [-h] [-v] [-m MODULE] [-l] [-c] [-s attr value] [-g attr]
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -v, --verbose         Show data about file and processing (Debug)
#   -m MODULE, --module MODULE
#                         selects the mode to run on
#   -l, --list            list configured modules
#   -c, --get-config      Get the configuration for the module
#   -s attr value, --set attr value
#                         Attribute value to set
#   -g attr, --get attr   get available values for this attribute
#
# ############################################################################

import win32security
import getpass
import winreg
from contextlib import suppress
import itertools
import sys
from enum import Enum
import argparse
import json

class ExtendedEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.name, cls))
    
class ScalingType(ExtendedEnum):
    "enum class ScalingType { None = 0, NIS, FSR, CAS, MaxValue };"
    Off     = 0
    NIS     = 1
    FSR     = 2
    CAS     = 3

class FirstRun(ExtendedEnum):
    Off     = 0
    On      = 8

class VariableShadingRateType(ExtendedEnum):
    Off     = 0
    Preset  = 1
    Custom  = 2

class VRSRatio(ExtendedEnum):
    x1      = 0
    x1_2    = 1
    x1_4    = 2
    x1_8    = 3
    x1_16   = 4   

class OnOff(ExtendedEnum):
    Off     = 0
    On      = 1

class DefaultOnOff(ExtendedEnum):
    Default = 0
    Off     = 1
    On      = 2

class MotionReprojectionRate(ExtendedEnum):
    " enum class MotionReprojectionRate { Off = 1, R_45Hz, R_30Hz, R_22Hz, MaxValue };"
    Off     = 1
    R_45Hz  = 2
    R_30Hz  = 3
    R_22Hz  = 4

class PostSunGlasses(ExtendedEnum):
    " enum class PostSunGlassesType { None = 0, Light, Dark, Night, MaxValue };"
    Off     = 0
    Light   = 1
    Dark    = 2
    Night   = 3

class OverlayType(ExtendedEnum):
    "enum class OverlayType { None = 0, FPS, Advanced, Developer, MaxValue };"
    Off       = 0
    FPS       = 1
    Advanced  = 2
    Developer = 3


def get_current_user_sid(username=None):

    if not username:
        username = getpass.getuser()
    
    sid = win32security.LookupAccountName(None, username)[0]
    sidstr = win32security.ConvertSidToStringSid(sid)
    return(sidstr)
        





# def traverse_key(path, hkey=winreg.HKEY_LOCAL_MACHINE, flags=0):
#     with suppress(WindowsError), winreg.OpenKey(hkey, path, 0, winreg.KEY_READ|flags) as k:
#         for i in itertools.count():
#             print(i)
#             yield winreg.EnumKey(k, i)

def get_subkeys(key, flags=0):
    with suppress(WindowsError), key:
        for i in itertools.count():
            yield winreg.EnumKey(key, i)

def get_values(key, flags=0):
    with suppress(WindowsError), key:
        for i in itertools.count():
            yield winreg.EnumValue(key, i)            



class OpenXRManager:
    def __init__(self):
        self.key_root = winreg.HKEY_CURRENT_USER
        self.openxr_path = r'SOFTWARE\OpenXR_Toolkit'
        self.openxr_key = OpenXRManager.check_key(self.openxr_path, reg_root=self.key_root)
        self.module_key = None

        if not self.openxr_key:
            print("Error: Can't read %s from registry" % self.openxr_path)
            sys.exit(-1)

        # some variables. See interfaces.h to get all the available data

        self.config_map = {}
        self.config_map['first_run2'] = FirstRun
        self.config_map['scaling_type'] = ScalingType
        self.config_map['vrs'] = VariableShadingRateType
        self.config_map['vrs_inner'] = VRSRatio
        self.config_map['vrs_middle'] = VRSRatio
        self.config_map['vrs_outer'] = VRSRatio
        self.config_map['turbo'] = OnOff
        self.config_map['override_resolution'] = OnOff
        self.config_map['expert_menu'] = OnOff
        self.config_map['overlay_show_clock'] = OnOff
        self.config_map['overlay'] = OverlayType
        self.config_map['motion_reprojection'] = DefaultOnOff
        self.config_map['motion_reprojection_rate'] = MotionReprojectionRate
        self.config_map['vrs_cull_mask'] = OnOff
        self.config_map['post_process'] = OnOff
        self.config_map['post_sunglasses'] = PostSunGlasses




        

    @staticmethod
    def check_key(path, reg_root = winreg.HKEY_CURRENT_USER, mode=winreg.KEY_READ):
        try:
            key = winreg.OpenKey(reg_root, path, 0, mode)
        except FileNotFoundError:
            return None
        return key

    @staticmethod
    def get_values(key, flags=0):
        with suppress(WindowsError), key:
            for i in itertools.count():
                yield winreg.EnumValue(key, i) 



    def list_modules(self):
        modules = []
        for k in get_subkeys(self.openxr_key):
            modules.append(k)
        return modules
    


    def set_value(self, module, attr, value):

        attr_found, options = self.get_options(attr)
        if attr_found and not value in options.list():
            print("Value: '%s' for attr '%s' is not valid. Avaliable options: %s" % (value, attr, ", ".join(options.list())))
            return False
        # set the registry key here.
        # and convert the value to the int representation of the enum
        value = options[value].value if options else value
        self.set_module_value(module, attr, value)
        return True
    

    def set_module_value(self, module, attr, value):

        # first, get the config
        cfg = self.get_module_config(module)
        attr_type = None
        for item in cfg:
            k_name, k_value, k_type = item
            if k_name == attr:
                attr_type = k_type
                # convert the value.
                if attr_type not in [ winreg.REG_SZ ]:
                    value = int(value)
                break
        
        if not attr_type:
            print("Can't find attr '%s' on module '%s'" % (attr, module))
            return None
            
        module_path = "%s\%s" % (self.openxr_path, module)
        module_key =  OpenXRManager.check_key(module_path, reg_root=self.key_root, mode=winreg.KEY_WRITE)
        winreg.SetValueEx(module_key, attr, 0, attr_type, value)
        winreg.CloseKey(module_key)

    def get_module_config(self, module):

        config = []
        module_path = "%s\%s" % (self.openxr_path, module)
        module_key =  OpenXRManager.check_key(module_path, reg_root=self.key_root)
        if not module_key:
            print("Error: Can't read %s from registry" % module_key)
            sys.exit(-1)

        for data in OpenXRManager.get_values(module_key):
            config.append( data )

        return config
    
    def map_data(self, data):
        
        n,v,t = data
        if n in self.config_map.keys():
            self.config_map[n] = self.config_map[n](v)
            return n, self.config_map[n].name, t
        
        return n,v,t
        
    def get_options(self, attr):

        if not attr.lower() in self.config_map.keys():
            return False,None
        return True, self.config_map[attr.lower()]

    def save_config(self, fname, config):
        
        data = json.dumps(config,indent=2)
        with open(fname,"w",encoding='UTF-8') as fd:
            fd.write(data)
            

    def read_from_file(self, fname):
        
        with open(fname,"r",encoding='UTF-8') as fd:
            data = fd.read()
        
        try:
            data = json.loads(data)
        except Exception as e:
            print("Can't load data from %s: %s" % (fname, e))
            sys.exit(-1)
        
        return data
                  
            
        

if __name__ == "__main__":


    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Show data about file and processing (Debug)", action="count", default=0)
    parser.add_argument("-m", "--module", help="selects the mode to run on", default="DCS World")
    parser.add_argument("-l", "--list", help="list configured modules", action="store_true")
    parser.add_argument("-f", "--file", help="read / write config to file (json format)")
    parser.add_argument("-c", "--get-config", help="Get the configuration for the module", action="store_true")

    parser.add_argument("-s", "--set",
                        nargs=2,
                        metavar=('attr','value'),
                        help="Attribute value to set")
    
    parser.add_argument("-g", "--get",
                        nargs=1,
                        metavar=('attr'),
                        help="get available values for this attribute")
    
    
    args = parser.parse_args()

    openXR = OpenXRManager()

    if args.list:
        modules = openXR.list_modules()
        print("Avaliable modules")
        for module in modules:
            print(" - %s" % module)
        sys.exit(0)

    if args.get_config:
        config = openXR.get_module_config(args.module)
        print("-" * 120)
        print("Module: %s" % args.module)
        print('{0:<25} {1}'.format("Key", "Value"))
        print("-" * 120)
        parsed_config = {}
        for data in config:
            k_name, k_value, k_type = openXR.map_data(data)
            print('{0:<25} {1}'.format(k_name, k_value))
            parsed_config[k_name] = k_value

        if args.file:
            openXR.save_config(args.file, parsed_config)
        sys.exit(0)

    if args.get:
        attr = args.get[0]
        options = openXR.get_options(attr)
        if not options:
            print("Attr: %s has no available options. Try -l" % attr)
            sys.exit(-1)
        print("Available options for %s: %s" % (attr, ", ".join(options.list())))
        sys.exit(0)

    if args.set:
        attr,value = args.set
        if not openXR.set_value(args.module, attr, value):
            sys.exit(0)     
    

    ## if here, and only -f ... read it and process all the file
    if args.file:
        config = openXR.read_from_file(args.file)
        for item in config.items():
            attr,value = item
            if not openXR.set_value(args.module, attr, value):
                continue