""" Handles getsentinel configuration

Provides the paths for all the internal workings of getsentinel.

Attributes
----------
ESA_USERNAME : str
    The ESA SciHub username for the user.
ESA_PASSWORD : str
    The ESA SciHub password for the user.
SEN2COR_ROOT_PATH : str
    Contains the aboslute filepath to the sen2cor installation.
GPT_ROOT_PATH : str
    The absolute filepath to the Sentinel Toolbox gpt utility.
DATA_PATH : str
    The relative or absolute filepath to the data storage directory.
QUICKLOOKS_PATH : str
    The relative or absolute filepath to the quicklooks storage directory.

"""

import os
import pathlib
import json


USER_INFO_DICT = {'user': 'ESA_username',
                  'passw': 'ESA_password',
                  'sen2cor': '/path/to/sen2cor/L2A_Process',
                  'gpt': '/path/to/gpt',
                  'data': '/path/to/store/data',
                  'qlooks': '/path/to/store/quicklooks',
                  'is_set': False}


def _get_config():
    """Loads in the config details from the gs_config.txt file."""

    if not pathlib.Path(CONFIG_PATH).exists():
        print("Config file does not exist. Creating gs_config.json in"
              " the installation directory.\n")
        print("Please re-run your script to be prompted for to enter config "
              "information.")
        set_userinfo(USER_INFO_DICT)
        raise RuntimeError("Config file does not exist. Creating gs_config.json in"
                           " the installation directory.\n"
                           "Please re-run your script to be prompted for to "
                           "enter config information.")
    with open(CONFIG_PATH, 'r') as config_file:
        config = json.load(config_file)

    keys = ['esa_username', 'esa_password', 'sen2cor_path', 'snap_gpt',
            'data_path', 'quicklooks_path', 'is_set']

    for key in keys:
        if key not in config:
            print("Config file is corrupted. Deleting config file.")
            pathlib.Path(CONFIG_PATH).unlink()
            set_userinfo(USER_INFO_DICT)
            raise RuntimeError("A config file error occured. Please re-run "
                               " your script and re-enter your config info.")
    if not config['is_set']:
        set_userinfo()
        config = _get_config()

    return config


def _ask_user(info_string, default=False):
    """Asks the user to enter the information for a certain config
    parameter."""

    request_string = "Please enter {0}:".format(info_string)
    if default:
        default_str = " (Press ENTER to use the default option {0}):".format(
            default)
        request_string = request_string[:-1] + default_str

    info = input(request_string)

    return info


def set_userinfo(info_dict=False):
    """Get the path and account info from the user.

    Note
    ----
    This function should be called to reset change the user config info.

    Parameters
    ----------
    info_dict : :obj:`dict` of :obj:`str`, optional
        If passed, must contain a `dict` of format contained in the global
        variable `USER_INFO_DICT`

    Returns
    -------
    None

    """

    # NOTE: consider adding hints on location of installation directories

    if info_dict:
        try:
            user = info_dict['user']
            passw = info_dict['passw']
            sen2cor = info_dict['sen2cor']
            gpt = info_dict['gpt']
            data = info_dict['data']
            qlooks = info_dict['qlooks']
            is_set = info_dict['is_set']
            _save_config(user, passw, sen2cor, gpt, data, qlooks, is_set)

            return
        
        except KeyError:
            raise KeyError("The dictionary passed to"
                           " gs_config.set_userinfo is not in the correct"
                           " format. Use the global variable"
                           " gs_config.USER_INFO_DICT for the example"
                           " structure.")

    user = _ask_user("your ESA SciHub username")
    passw = _ask_user("your ESA SciHub password")
    sen2cor = _ask_user("the absolute path to your ESA sen2cor installation "
                        "L2A_Process tool")
    # Check to see if L2A_Process tool exists at the file path
    while True:
        sen2cor_path = pathlib.Path(sen2cor)
        if sen2cor_path.exists() and sen2cor_path.stem == 'L2A_Process':
            break
        print("Could not find the L2A_Process file at that location.")
        sen2cor = _ask_user("the absolute path to your ESA sen2cor "
                            "installation L2A_Process tool")

    gpt = _ask_user("the absolute path to your SNAP installation gpt tool")
    # Check to see if gpt tool exists at the file path
    while True:
        gpt_path = pathlib.Path(gpt)
        if gpt_path.exists() and gpt_path.stem == 'gpt':
            break
        print("Could not find the gpt file at that location.")
        gpt = _ask_user("the absolute path to your SNAP installation gpt tool")

    default = 'data/'
    data = _ask_user("the path where you want your Sentinel data to be stored",
                     default)
    if not data:
        data = default
    default = 'quicklooks/'
    qlooks = _ask_user("the path where you want Sentinel product"
                       " quicklooks to be stored",
                       default)
    if not qlooks:
        qlooks = default

    _save_config(user, passw, sen2cor, gpt, data, qlooks, is_set=True)


def _save_config(user, passw, sen2cor, gpt, data, qlooks, is_set = False):
    """Saves all the details to the config file."""

    config = {}
    config['esa_username'] = user
    config['esa_password'] = passw
    config['sen2cor_path'] = sen2cor
    config['snap_gpt'] = gpt
    config['data_path'] = data
    config['quicklooks_path'] = qlooks
    config['is_set'] = is_set

    with open(CONFIG_PATH, 'w') as config_file:
        json.dump(config, config_file)


INSTALL_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(INSTALL_PATH, 'gs_config.json')

_config_info = _get_config()

ESA_USERNAME = _config_info['esa_username']
ESA_PASSWORD = _config_info['esa_password']
SEN2COR_ROOT_PATH = _config_info['sen2cor_path']
GPT_ROOT_PATH = _config_info['snap_gpt']
DATA_PATH = _config_info['data_path']
QUICKLOOKS_PATH = _config_info['quicklooks_path']
