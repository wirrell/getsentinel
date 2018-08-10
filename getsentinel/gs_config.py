"""getsentinel configuration

Provides the paths for all the internal workings of getsentinal.
Example structure:

    *getsentinel config file*
    esa_username=username
    esa_password=password
    sen2core_path=/path/to/sen2core
    snap_gpt=/path/to/snap/gpt
    data_path=/path/tostore/alldownloaddata
    quicklooks_path=/path/to/store/all/quicklooks
    s1graph_path=/path/to/s1processing/xmlfiles
    s2graph_path=/path/to/s2processing/xmlsfiles

"""

import os
import pathlib


def _get_config():
    """Loads in the config details from the gs_config.txt file."""

    if not pathlib.Path(CONFIG_PATH).exists():
        print("Config file does not exist. Please enter the following"
              " details:\n")
        _get_userinfo()
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


def ask_user(info_string, default=False):
    """Asks the user to enter the information for a certain config
    parameter.

    Parameters
    ----------
    info_string : str
        Describes the information required from the user
    default : bool
        If true, offers user the default option

    Returns
    -------
    info : str
        The information entered by the user in response to the question.
    """

    request_string = "Please enter {0}:".format(info_string)
    if default:
        default_str = " (Press ENTER to use the default option {0}):".format(
            default)
        request_string = request_string[:-1] + default_str

    info = input(request_string)

    return info


def _get_userinfo():
    """Get the path and account info from the user."""

    # NOTE: consider adding hints on location of installation directories

    user = ask_user("your ESA SciHub username")
    passw = ask_user("your ESA SciHub password")
    sen2cor = ask_user("the absolute path to your ESA sen2cor installation")
    gpt = ask_user("the absolute path to your SNAP installation gpt tool")
    default = 'data/'
    data = ask_user("the path where you want your Sentinel data to be stored",
                    default)
    if not data:
        data = default
    default = 'quicklooks/'
    qlooks = ask_user("the path where you want Sentinel product"
                      " quicklooks to be stored",
                      default)
    if not qlooks:
        qlooks = default
    default = 's1graphs/'
    s1graphs = ask_user("the path to the SNAP Sentinel-1 graph files",
                        default)
    if not s1graphs:
        s1graphs = default
    default = 's2graphs/'
    s2graphs = ask_user("the path to the SNAP Sentinel-2 graph files",
                        default)
    if not s2graphs:
        s2graphs = default

    _save_config(user, passw, sen2cor, gpt, data, qlooks, s1graphs, s2graphs)


def _save_config(user, passw, sen2cor, gpt, data, qlooks, s1graphs, s2graphs):
    """Saves all the details to the config file."""

    config_string = ("*getsentinel config file*\n"
                     "esa_username={0}\n"
                     "esa_password={1}\n"
                     "sen2core_path={2}\n"
                     "snap_gpt={3}\n"
                     "data_path={4}\n"
                     "quicklooks_path={5}\n"
                     "s1graph_path={6}\n"
                     "s2graph_path={7}")

    config_string = config_string.format(user, passw, sen2cor, gpt, data,
                                         qlooks, s1graphs, s2graphs)

    with open(CONFIG_PATH, 'w') as config_file:
        config_file.write(config_string)


INSTALL_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(INSTALL_PATH, 'gs_config.txt')

_config_info = _get_config()

ESA_USERNAME = _config_info[0]
ESA_PASSWORD = _config_info[1]
SEN2COR_ROOT_PATH = _config_info[2]
GPT_ROOT_PATH = _config_info[3]
DATA_PATH = _config_info[4]
QUICKLOOKS_PATH = _config_info[5]
S1GRAPHS_PATH = _config_info[6]
S2GRAPHS_PATH = _config_info[7]
