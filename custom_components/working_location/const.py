"""Constants for the Google Calendar Working Location integration."""

DOMAIN = "working_location"

# Config/options keys
CONF_CALENDAR_ID = "calendar_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_CONSIDER_NONE_OUTSIDE_HOURS = "consider_none_outside_hours"

# Defaults
DEFAULT_CALENDAR_ID = "primary"
DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_CONSIDER_NONE_OUTSIDE_HOURS = False

# OAuth
OAUTH2_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"

# API
CALENDAR_API_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
)

# Sensor states
STATE_HOME_OFFICE = "homeOffice"
STATE_OFFICE_LOCATION = "officeLocation"
STATE_CUSTOM_LOCATION = "customLocation"
STATE_NONE = "none"
STATE_UNKNOWN = "unknown"

VALID_STATES = {STATE_HOME_OFFICE, STATE_OFFICE_LOCATION, STATE_CUSTOM_LOCATION}
