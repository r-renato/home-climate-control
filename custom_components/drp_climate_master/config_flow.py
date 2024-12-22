import logging

from homeassistant import config_entries
from .const import (
    DOMAIN    
)
_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class HomeClimateMasterConfigFlow(config_entries.ConfigFlow):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="DRP Home Climate Master", data={})