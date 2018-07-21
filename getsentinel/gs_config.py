# Config file

SEN2COR_ROOT_PATH='/Users/joefennell/documents/Sen2Cor-02.05.05-Darwin64/bin/L2A_Process'
#DATA_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat'
DATA_PATH = '/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat/'
#QUICKLOOKS_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat/quicklooks'
QUICKLOOKS_PATH = 'quicklooks/'
S1GRAPHS_PATH = 's1_graphs/'

def _getlogin():
    try:
        with open('esa_user_info.txt', 'r') as f:
            info = f.readline()
            [user, password] = [x.strip() for x in info.split(':')]
            return user, password
    except FileNotFoundError:
        print("No current esa_user_info.txt file found.\n")
        user = input("Please enter your ESA SciHub username: ")
        password = input("Please enter your ESA SciHub password: ")
        print("Creating esa_user_info.txt file required.")
        with open('esa_user_info.txt', 'w') as f:
            print(user + ':' + password, file=f)
        return user, password
ESA_USERNAME, ESA_PASSWORD = _getlogin()
