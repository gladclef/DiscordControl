from datetime import datetime, timedelta
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

class Fresh(Generic[T]):
    """ Wrapper class to ensure that the stored value
    is always new within a given expiration_time time window. """

    def __init__(self, getter: Callable[[], T], expiration_time: timedelta | None = timedelta(seconds=10), expiration_ref_obj: Callable = None):
        self.getter = getter
        self.expiration_time = expiration_time
        self.expiration_ref_obj = expiration_ref_obj
        self.last_ref_obj = None
        
        self.curr_val: T = None
        self.needs_refresh = True
        self.last_access_time: datetime = None
        self.is_locked = False

    @property
    def is_expired(self) -> bool:
        is_expired = False

        if self.expiration_time is not None:
            is_expired = is_expired or (self.last_access_time + self.expiration_time < datetime.now())
        if self.expiration_ref_obj is not None:
            obj = self.expiration_ref_obj()
            if obj is None:
                if self.last_ref_obj is not None:
                    is_expired = False
            elif obj is not None:
                if self.last_ref_obj is None:
                    is_expired = False
                else:
                    is_expired = is_expired or (obj != self.last_ref_obj)
        
        return is_expired

    def _get_fresh_value(self):
        self.curr_val = self.getter()
        self.needs_refresh = False

        self.last_access_time = datetime.now()
        if self.expiration_ref_obj is not None:
            self.last_ref_obj = self.expiration_ref_obj()
    
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
    
