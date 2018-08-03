<<<<<<< HEAD
# Config file
GPT_ROOT_PATH= '/Applications/snap/bin/gpt'
SEN2COR_ROOT_PATH='/Users/joefennell/documents/Sen2Cor-02.05.05-Darwin64/bin/L2A_Process'
DATA_PATH='/Users/joefennell/Documents/data'
=======
"""getsentinel configuration

Provides the paths for all the internal workings of getsentinal.
Example structure:

    *getsentinel config file*    
    esa_username=userame
    esa_password=password
    sen2core_path=/path/to/sen2core
    snap_gpt=/path/to/snap/gpt
    data_path=/path/tostore/alldownloaddata
    quicklooks_path=/path/to/store/all/quicklooks
    s1graph_path-/path/to/s1processing/xmlfiles
    
TODO
----
Implement above new config.txt format"""

SEN2COR_ROOT_PATH='/Users/joefennell/documents/Sen2Cor-02.05.05-Darwin64/bin/L2A_Process'
SNAP_GPT='/home/george/snap/bin/gpt'
DATA_PATH='/run/media/george/Maxtor/George/sentinel_data/s1_winterwheat/'
>>>>>>> george
#DATA_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat'
#DATA_PATH = '/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat/'
#QUICKLOOKS_PATH='/run/media/george/TOSHIBA_EXT/sentinel_data/s1_winterwheat/quicklooks'
QUICKLOOKS_PATH = 'quicklooks/'

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

