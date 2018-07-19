# Config file

SEN2COR_ROOT_PATH='/Users/joefennell/documents/Sen2Cor-02.05.05-Darwin64/bin/L2A_Process'
#DATA_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat'
DATA_PATH = 'data/'
#QUICKLOOKS_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat/quicklooks'
QUICKLOOKS_PATH = 'quicklooks/'
S1GRAPHS_PATH = 's1_graphs/'

def _getlogin():
    try:
        with open('user_info.txt', 'r') as f:
            info = f.readline()
            [user, password] = [x.strip() for x in info.split(':')]
            return user, password
    except FileNotFoundError:
        print("user_info.txt file required in containing 'username:password'")
        raise
ESA_USERNAME, ESA_PASSWORD = _getlogin()
