"""
Downloaded product inventory manager.
"""

import inspect
import json
from pathlib import Path
from functools import wraps

def check_integrity(func):
    
    """Decorator which checks the integrity of the current inventory."""

    sig = inspect.signature(func)

    if 'download_dir' not in sig.parameters:
        raise ValueError("No download directory specified.")

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        download_dir = Path(bound_args.arguments['download_dir'])
        download_dir.mkdir(exist_ok=True)
        inventory_location = Path(str(download_dir)
                                  + '/product_inventory.json')

        if not inventory_location.exists():
            inventory_location.touch()
            return func(*args, **kwargs)
        try:
            with inventory_location.open() as read_file:
                inventory = json.load(read_file)
        except ValueError:
            pass #TODO
        


        return func(*args, **kwargs)



    return wrapper

@check_integrity
def get_inventory(download_dir : str):

    """Retrieves and reads in the product_inventory.json file. """

    pass





if __name__ == '__main__':
    get_inventory('test')

