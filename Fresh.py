from datetime import datetime, timedelta
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

class Fresh(Generic[T]):
    """ Wrapper class to ensure that the stored value
    is always new within a given expiration time window. """

    def __init__(self, getter: Callable[[], T], expiration: timedelta = timedelta(seconds=10)):
        self.getter = getter
        self.expiration = expiration
        
        self.curr_val: T = None
        self.needs_refresh = True
        self.last_access_time: datetime = None
        self.is_locked = False

    @property
    def is_expired(self) -> bool:
        return self.last_access_time + self.expiration < datetime.now()

    def _get_fresh_value(self):
        self.curr_val = self.getter()
        self.needs_refresh = False
        self.last_access_time = datetime.now()
    
    def get(self):
        if self.needs_refresh:
            self._get_fresh_value()
        
        elif self.is_expired:
            if not self.is_locked:
                self._get_fresh_value()
        
        return self.curr_val
    
    def lock(self):
        """ Prevents this instance from being refreshed when expired. """
        self.is_locked = True
    
    def unlock(self):
        """ Allow this instance to be refreshed when expired. """
        self.is_locked = False
    
