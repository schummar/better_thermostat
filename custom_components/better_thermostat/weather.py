import logging
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.recorder import history

from .models.utils import convert_to_float

_LOGGER = logging.getLogger(__name__)


async def check_weather(self):
	# check weather predictions or ambient air temperature if available
	if self.weather_entity is not None:
		return check_weather_prediction(self)
	elif self.outdoor_sensor is not None:
		return check_ambient_air_temperature(self)
	else:
		# no weather evaluation: call for heat is always true
		return True


def check_weather_prediction(self):
	"""
	Checks configured weather entity for next two days of temperature predictions.
	@return: True if the maximum forcast temperature is lower than the off temperature; None if not successful
	"""
	if self.weather_entity is None:
		_LOGGER.warning(f"better_thermostat {self.name}: weather entity not available.")
		return None
	
	if self.off_temperature is None or not isinstance(self.off_temperature, float):
		_LOGGER.warning(f"better_thermostat {self.name}: off_temperature not set or not a float.")
		return None
	
	try:
		forcast = self.hass.states.get(self.weather_entity).attributes.get('forecast')
		if len(forcast) > 0:
			max_forcast_temp = int(
				round(
					(convert_to_float(forcast[0]['temperature'], self.name, "check_weather_prediction()")
					 + convert_to_float(forcast[1]['temperature'], self.name, "check_weather_prediction()")) / 2
				)
			)
			return max_forcast_temp < self.off_temperature
		else:
			raise TypeError
	except TypeError:
		_LOGGER.warning(f"better_thermostat {self.name}: no weather entity data found.")
		return None


def check_ambient_air_temperature(self):
	"""
	Gets the history for two days and evaluates the necessary for heating.
	@return: returns True if the average temperature is lower than the off temperature; None if not successful
	"""
	if self.outdoor_sensor is None:
		return None
	
	if self.off_temperature is None or not isinstance(self.off_temperature, float):
		_LOGGER.warning(f"better_thermostat {self.name}: off_temperature not set or not a float.")
		return None
	
	try:
		last_two_days_date_time = datetime.now() - timedelta(days=2)
		start = dt_util.as_utc(last_two_days_date_time)
		history_list = history.state_changes_during_period(
			self.hass, start, dt_util.as_utc(datetime.now()), self.outdoor_sensor
		)
		historic_sensor_data = history_list.get(self.outdoor_sensor)
	except TypeError:
		_LOGGER.warning(f"better_thermostat {self.name}: no outdoor sensor data found.")
		return None
	
	# create a list from valid data in historic_sensor_data
	valid_historic_sensor_data = []
	for measurement in historic_sensor_data:
		if measurement.state is not None:
			try:
				valid_historic_sensor_data.append(convert_to_float(measurement.state, self.name, "check_ambient_air_temperature()"))
			except ValueError:
				pass
			except TypeError:
				pass
	
	if len(valid_historic_sensor_data) == 0:
		_LOGGER.warning(f"better_thermostat {self.name}: no valid outdoor sensor data found.")
		return None
	
	# remove the upper and lower 5% of the data
	valid_historic_sensor_data.sort()
	valid_historic_sensor_data = valid_historic_sensor_data[
	                             int(round(len(valid_historic_sensor_data) * 0.05)):int(round(len(valid_historic_sensor_data) * 0.95))]
	
	if len(valid_historic_sensor_data) == 0:
		_LOGGER.warning(f"better_thermostat {self.name}: no valid outdoor sensor data found.")
		return None
	
	# calculate the average temperature
	avg_temp = int(round(sum(valid_historic_sensor_data) / len(valid_historic_sensor_data)))
	_LOGGER.debug(f"better_thermostat {self.name}: avg outdoor temp: %s", avg_temp)
	return avg_temp < self.off_temperature
