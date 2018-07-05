# Config file

SEN2COR_ROOT_PATH='/Users/joefennell/documents/Sen2Cor-02.05.05-Darwin64/bin/L2A_Process'
DATA_PATH='data/'
QUICKLOOKS_PATH='quicklooks/'
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
