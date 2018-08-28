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


def _get_config():
    """Loads in the config details from the gs_config.txt file."""

    if not pathlib.Path(CONFIG_PATH).exists():
        print("Config file does not exist. Please enter the following"
              " details:\n")
        set_userinfo()
    with open(CONFIG_PATH, 'r') as config_file:
        data = config_file.read()
        data = data.split('\n')[1:]

    config_info = []

    for i in range(len(data)):
        data[i] = data[i].split('=')
        if len(data[i]) is not 2:
            error_msg = ("Config file is corrupted. Deleting the config file."
                         "\n Re-run this script to re-enter the config"
                         " details. \n")
            pathlib.Path(CONFIG_PATH).unlink()
            raise RuntimeError(error_msg)
        config_info.append(data[i][1])

    return config_info


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
            _save_config(user, passw, sen2cor, gpt, data, qlooks)

            return
        except KeyError:
            raise KeyError("The dictionary passed to"
                           " gs_config.set_userinfo is not in the correct"
                           " format. Use the global variable"
                           " gs_config.USER_INFO_DICT for the example"
                           " structure.")

    user = _ask_user("your ESA SciHub username")
    passw = _ask_user("your ESA SciHub password")
    sen2cor = _ask_user("the absolute path to your ESA sen2cor installation")
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

    _save_config(user, passw, sen2cor, gpt, data, qlooks)


def _save_config(user, passw, sen2cor, gpt, data, qlooks):
    """Saves all the details to the config file."""

    config_string = ("*getsentinel config file*\n"
                     "esa_username={0}\n"
                     "esa_password={1}\n"
                     "sen2core_path={2}\n"
                     "snap_gpt={3}\n"
                     "data_path={4}\n"
                     "quicklooks_path={5}\n")

    config_string = config_string.format(user, passw, sen2cor, gpt, data,
                                         qlooks)

    with open(CONFIG_PATH, 'w') as config_file:
        config_file.write(config_string)


INSTALL_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(INSTALL_PATH, 'gs_config.txt')

_config_info = _get_config()

USER_INFO_DICT = {'user': 'ESA_username',
                  'passw': 'ESA_password',
                  'sen2cor': '/path/to/sen2cor',
                  'gpt': '/path/to/gpt',
                  'data': '/path/to/store/data',
                  'qlooks': '/path/to/store/quicklooks'}

ESA_USERNAME = _config_info[0]
ESA_PASSWORD = _config_info[1]
SEN2COR_ROOT_PATH = _config_info[2]
GPT_ROOT_PATH = _config_info[3]
DATA_PATH = _config_info[4]
QUICKLOOKS_PATH = _config_info[5]
