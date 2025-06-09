from odoo import models, fields, api
import requests
import logging
from odoo.exceptions import UserError
import time

_logger = logging.getLogger(__name__)

class ProfileDriver(models.Model):
    _name = 'profile.driver'
    _description = 'Driver Profile'
    _rec_name = 'driver_number'
    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'External ID must be unique.'),
    ]

    external_id = fields.Integer(string='External ID', required=True, index=True)
    first_name = fields.Char(string='First Name', required=True)
    last_name = fields.Char(string='Last Name', required=True)
    phone_number = fields.Char(string='Phone Number', required=True)
    driver_number = fields.Char(string='Driver Number', required=True)
    rides = fields.Char(string='Rides')  # Stored as JSON string
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    last_sync = fields.Datetime(string='Last Synced', readonly=True)

    @api.model
    def create(self, values):
        """Override create to ensure external_id is set via API."""
        if 'external_id' not in values or not values['external_id']:
            existing = self.search([
                ('phone_number', '=', values.get('phone_number')),
                ('username', '=', values.get('username'))
            ], limit=1)
            if existing:
                raise UserError(f"Driver with phone number {values.get('phone_number')} and username {values.get('username')} already exists (external ID: {existing.external_id}).")
            external_id = self._create_driver_via_api(values)
            values['external_id'] = external_id
        if self.search([('external_id', '=', values['external_id'])], limit=1):
            raise UserError(f"Driver with external ID {values['external_id']} already exists in Odoo.")
        return super(ProfileDriver, self).create(values)

    def write(self, values):
        """Override write to call update_driver after local update."""
        result = super(ProfileDriver, self).write(values)
        for record in self:
            try:
                # Skip API update if triggered by sync to avoid loops
                if self._context.get('from_sync'):
                    _logger.debug("Skipping API update for driver %s during sync", record.id)
                    continue
                # Call update_driver with the updated values
                self.update_driver(record.id, values)
                _logger.info("Driver %s updated via API after local write", record.id)
            except Exception as e:
                _logger.error("Failed to update driver %s via API: %s", record.id, str(e))
                # Optionally raise an error to notify the user
                # raise UserError(f"Failed to update driver via API: {str(e)}")
        return result

    @api.model
    def fetch_driver_list(self):
        """Fetch and return the list of drivers from the API."""
        api_url = 'http://147.93.52.105:9082/api/v1/profile/driver'
        try:
            _logger.info("Fetching driver list from API: %s", api_url)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=10)
            _logger.info("API GET %s response: %s status: %s", api_url, response.text, response.status_code)
            
            if response.status_code != 200:
                _logger.error("Failed to fetch driver list: %s status: %s", response.text, response.status_code)
                raise UserError(f"Failed to fetch driver list: {response.text} status: {response.status_code}")
            
            drivers = response.json()
            if not isinstance(drivers, list):
                _logger.error("Invalid API response format: Expected list, got %s", type(drivers).__name__)
                raise UserError(f"Invalid API response format: Expected list, got {type(drivers).__name__}")

            driver_ids = []
            sync_time = fields.Datetime.now()
            for driver in drivers:
                external_id = driver.get('id', 0)
                if not external_id:
                    _logger.warning("Skipping driver with missing id: %s", driver)
                    continue
                
                driver_data = {
                    'external_id': external_id,
                    'first_name': driver.get('firstName'),
                    'last_name': driver.get('lastName'),
                    'phone_number': driver.get('phoneNumber', ''),
                    'driver_number': driver.get('driverNumber', ''),
                    'rides': str(driver.get('rides', [])),
                    'username': driver.get('username', ''),
                    'password': driver.get('password', ''),
                    'last_sync': sync_time,
                }
                
                existing = self.search([('external_id', '=', external_id)], limit=1)
                if existing:
                    existing.with_context(from_sync=True).write(driver_data)
                    driver_ids.append(existing.id)
                    _logger.debug("Updated driver with external_id: %s", external_id)
                else:
                    new_record = self.create(driver_data)
                    driver_ids.append(new_record.id)
                    _logger.debug("Created new driver with external_id: %s", external_id)

            _logger.info("Synced %s driver records", len(driver_ids))
            return self.browse(driver_ids)
        except requests.RequestException as e:
            _logger.error("API request failed for driver list: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def fetch_filtered_drivers(self, first_name=None, last_name=None):
        """Fetch drivers from API filtered by first_name or last_name, with local fallback."""
        api_url = 'http://147.93.52.105:9082/api/v1/profile/driver/filter'
        params = {}
        if first_name:
            params['first_name'] = first_name.strip()
            params['firstName'] = first_name.strip()
        if last_name:
            params['last_name'] = last_name.strip()
            params['lastName'] = last_name.strip()
        
        try:
            _logger.info("Fetching filtered drivers from API: %s with params: %s", api_url, params)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, params=params, timeout=10)
            _logger.info("API GET %s response: %s status: %s", api_url, response.text, response.status_code)
            
            if response.status_code != 200:
                _logger.error("Failed to fetch filtered drivers: %s status: %s", response.text, response.status_code)
                raise UserError(f"Failed to fetch filtered drivers: {response.text} status: {response.status_code}")
            
            drivers = response.json()
            if not isinstance(drivers, list):
                _logger.error("Invalid API response format: Expected list, got %s", type(drivers).__name__)
                raise UserError(f"Invalid API response format: Expected list, got {type(drivers).__name__}")

            driver_ids = []
            sync_time = fields.Datetime.now()
            for driver in drivers:
                external_id = driver.get('id', 0)
                if not external_id:
                    _logger.warning("Skipping driver with missing id: %s", driver)
                    continue
                
                driver_data = {
                    'external_id': external_id,
                    'first_name': driver.get('firstName'),
                    'last_name': driver.get('lastName'),
                    'phone_number': driver.get('phoneNumber', ''),
                    'driver_number': driver.get('driverNumber', ''),
                    'rides': str(driver.get('rides', [])),
                    'username': driver.get('username', ''),
                    'password': driver.get('password', ''),
                    'last_sync': sync_time,
                }
                
                existing = self.search([('external_id', '=', external_id)], limit=1)
                if existing:
                    existing.with_context(from_sync=True).write(driver_data)
                    driver_ids.append(existing.id)
                    _logger.debug("Updated driver with external_id: %s", external_id)
                else:
                    new_record = self.create(driver_data)
                    driver_ids.append(new_record.id)
                    _logger.debug("Created new driver with external_id: %s", external_id)

            filtered_drivers = self.browse(driver_ids)
            if first_name or last_name:
                valid_results = True
                for driver in filtered_drivers:
                    if first_name and not (first_name.lower() in (driver.first_name or '').lower()):
                        valid_results = False
                        _logger.warning("API returned driver %s with first_name %s, does not match filter %s",
                                        driver.external_id, driver.first_name, first_name)
                    if last_name and not (last_name.lower() in (driver.last_name or '').lower()):
                        valid_results = False
                        _logger.warning("API returned driver %s with last_name %s, does not match filter %s",
                                        driver.external_id, driver.last_name, last_name)
                
                if not valid_results:
                    _logger.info("API filter returned incorrect results, falling back to local filtering")
                    domain = []
                    if first_name:
                        domain.append(('first_name', 'ilike', f'%{first_name}%'))
                    if last_name:
                        domain.append(('last_name', 'ilike', f'%{last_name}%'))
                    filtered_drivers = self.search(domain)
                    driver_ids = filtered_drivers.ids
                    _logger.info("Local filtering returned %s drivers", len(driver_ids))

            _logger.info("Fetched %s filtered driver records", len(driver_ids))
            return filtered_drivers
        except requests.RequestException as e:
            _logger.error("API request failed for filtered drivers: %s", str(e))
            _logger.info("Falling back to local driver search")
            domain = []
            if first_name:
                domain.append(('first_name', 'ilike', f'%{first_name}%'))
            if last_name:
                domain.append(('last_name', 'ilike', f'%{last_name}%'))
            drivers = self.search(domain)
            _logger.info("Local fallback search returned %s drivers", len(drivers))
            return drivers
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def fetch_driver_details(self, external_id):
        """Fetch details of a specific driver by ID."""
        api_url = f'http://147.0.93.52.105:9082/api/v1/profile/driver/{external_id}'
        try:
            _logger.info("Fetching driver details from API: %s", api_url)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=10)
            _logger.info("API GET %s response: %s status: %s", api_url, response.text, response.status_code)
            
            if response.status_code == 404:
                _logger.warning("Driver not found for external_id: %s", external_id)
                raise UserError("Driver not found")
            if response.status_code != 200:
                _logger.error("Failed to fetch driver details: %s status: %s", response.text, response.status_code)
                raise UserError(f"Failed to fetch driver details: %s status: %s", response.text, response.status_code)
            
            driver = response.json()
            if not isinstance(driver, dict):
                _logger.error("Invalid API response format: Expected dict, got %s", type(driver).__name__)
                raise UserError(f"Invalid API response format: {type(driver).__name__}")

            driver_data = {
                'external_id': driver.get('id', 0),
                'first_name': driver.get('firstName'),
                'last_name': driver.get('lastName'),
                'phone_number': driver.get('phoneNumber', ''),
                'driver_number': driver.get('driverNumber', ''),
                'rides': str(driver.get('rides', [])),
                'username': driver.get('username', ''),
                'password': driver.get('password', ''),
                'last_sync': fields.Datetime.now(),
            }

            existing = self.search([('external_id', '=', driver.get('id', 0))], limit=1)
            if existing:
                existing.with_context(from_sync=True).write(driver_data)
                driver_id = existing.id
                _logger.debug("Updated driver with external_id: %s", driver.get('id'))
            else:
                driver_record = self.create(driver_data)
                driver_id = driver_record.id
                _logger.debug("Created driver with external_id: %s", driver.get('id'))

            _logger.info("Fetched and processed driver record with external_id: %s", driver_id)
            return driver_id
        except requests.RequestException as e:
            _logger.error("API request failed for driver details: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def _create_driver_via_api(self, values):
        """Create a new driver via API and return external_id."""
        api_url = 'http://147.93.52.105:9082/api/v1/profile/driver'
        try:
            driver_data = {
                'firstName': values.get('first_name'),
                'lastName': values.get('last_name'),
                'phoneNumber': values.get('phone_number'),
                'driverNumber': values.get('driver_number'),
                'rides': eval(values.get('rides', '[]')),
                'username': values.get('username'),
                'password': values.get('password'),
            }
            _logger.info("Creating driver via API: %s with data: %s", api_url, driver_data)
            headers = {'Content-Type': 'application/json'}
            response = requests.post(api_url, json=driver_data, headers=headers, timeout=10)
            _logger.info("API POST %s response: %s status: %s", api_url, response.text, response.status_code)

            if response.status_code != 201:
                _logger.error("Failed to create driver: %s status: %s", response.text, response.status_code)
                raise UserError(f"Failed to create driver: %s status: %s", response.text, response.status_code)

            time.sleep(2)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=10)
            if response.status_code != 200:
                raise UserError(f"Failed to fetch driver list after creation: %s status: %s", response.text, response.status_code)
            drivers = response.json()
            if not drivers:
                raise UserError("No drivers found in API after creation")

            matching_drivers = [
                driver for driver in drivers
                if (driver.get('phoneNumber') == driver_data['phoneNumber'] and
                    driver.get('username') == driver_data['username'] and
                    driver.get('firstName') == driver_data['firstName'] and
                    driver.get('lastName') == driver_data['lastName'] and
                    driver.get('driverNumber') == driver_data['driverNumber'])
            ]

            if not matching_drivers:
                _logger.error("No matching driver found for data: %s", driver_data)
                raise UserError("Could not identify new driver in API response. Please check API data consistency.")

            new_driver = max(matching_drivers, key=lambda d: d['id'])
            external_id = new_driver.get('id')
            _logger.info("Identified new driver with external_id: %s", external_id)

            if self.search([('external_id', '=', external_id)], limit=1):
                _logger.error("External ID %s already exists in Odoo", external_id)
                raise UserError(f"Driver with external ID %s already exists in Odoo.", external_id)

            return external_id

        except requests.RequestException as e:
            _logger.error("API request failed for driver creation: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def update_driver(self, driver_id, values):
        """Update a driver via API."""
        driver = self.browse(driver_id)
        if not driver.exists():
            _logger.error("Driver with ID %s not found in Odoo", driver_id)
            raise UserError("Driver not found")
        
        api_url = 'http://147.93.52.105:9082/api/v1/profile/driver'
        try:
            # Handle rides field
            rides = values.get('rides', driver.rides or '[]')
            try:
                rides_list = eval(rides) if isinstance(rides, str) else rides
                if not isinstance(rides_list, list):
                    _logger.error("Rides data for driver %s is not a list: %s", driver_id, rides_list)
                    raise ValueError("Rides must be a list")
            except (ValueError, SyntaxError) as e:
                _logger.error("Invalid rides data for driver %s: %s", driver_id, str(e))
                raise UserError(f"Invalid rides data: {str(e)}")

            # Prepare API payload with all required fields
            driver_data = {
                'id': driver.external_id,
                'firstName': values.get('first_name', driver.first_name) or '',
                'lastName': values.get('last_name', driver.last_name) or '',
                'phoneNumber': values.get('phone_number', driver.phone_number) or '',
                'driverNumber': values.get('driver_number', driver.driver_number) or '',
                'rides': rides_list,
                'username': values.get('username', driver.username) or '',
                'password': values.get('password', driver.password) if values.get('password') else driver.password or '',
            }

            # Validate required fields as per Swagger schema
            required_fields = ['firstName', 'lastName', 'phoneNumber', 'driverNumber', 'rides', 'username', 'password']
            missing = [field for field in required_fields if driver_data[field] is None or driver_data[field] == '']
            if missing:
                _logger.error("Missing required fields for driver %s API update: %s", driver_id, ', '.join(missing))
                raise UserError(f"Missing required fields for API update: {', '.join(missing)}")

            _logger.info("Updating driver via API: %s with data: %s", api_url, driver_data)
            headers = {'Content-Type': 'application/json'}
            response = requests.put(api_url, json=driver_data, headers=headers, timeout=10)
            _logger.info("API PUT %s response: %s status: %s", api_url, response.text, response.status_code)

            if response.status_code != 201:
                _logger.error("Failed to update driver %s: %s status: %s", driver_id, response.text, response.status_code)
                raise UserError(f"Failed to update driver: {response.text} status: {response.status_code}")

            if response.text.strip() != '"Driver Successfully Updated"':
                _logger.warning("Unexpected API response for driver %s update: %s", driver_id, response.text)

            # Update local record
            local_values = {
                'first_name': driver_data['firstName'],
                'last_name': driver_data['lastName'],
                'phone_number': driver_data['phoneNumber'],
                'driver_number': driver_data['driverNumber'],
                'rides': str(driver_data['rides']),
                'username': driver_data['username'],
                'last_sync': fields.Datetime.now(),
            }
            if values.get('password'):
                local_values['password'] = driver_data['password']
            driver.with_context(from_sync=True).write(local_values)
            _logger.info("Successfully updated driver with external_id: %s in Odoo and API", driver.external_id)
            return driver.id
        except requests.RequestException as e:
            _logger.error("API request failed for driver %s update: %s", driver_id, str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response or rides data for driver %s: %s", driver_id, str(e))
            raise UserError(f"Invalid API response or rides data: {str(e)}")

    def unlink(self):
        """Override unlink to handle API deletion before local deletion."""
        if self._context.get('from_sync'):
            _logger.info("Skipping API delete for driver during sync: %s", self.phone_number)
            return super(ProfileDriver, self).unlink()

        for record in self:
            if record.external_id:
                try:
                    api_url = f'http://147.93.52.105:9082/api/v1/profile/driver/{record.external_id}'
                    _logger.info("Sending DELETE request to: %s", api_url)
                    response = requests.delete(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    _logger.info("API DELETE %s response: %s (Status: %s)", api_url, response.text, response.status_code)
                    if response.status_code not in (200, 204):
                        _logger.warning(
                            "Failed to delete driver %s in API: %s (Status: %s). Proceeding with Odoo deletion.",
                            record.phone_number or record.id, response.text, response.status_code
                        )
                except requests.RequestException as e:
                    _logger.error("API DELETE request failed for driver %s: %s.", record.phone_number or record.id, str(e))
            else:
                _logger.info("Skipping API delete for driver %s: No external_id.", record.phone_number or record.id)

        return super(ProfileDriver, self).unlink()

    @api.model
    def sync_drivers(self):
        """Sync driver data from API, used by cron job."""
        try:
            _logger.info("Starting driver data sync via cron")
            sync_start_time = fields.Datetime.now()
            drivers = self.fetch_driver_list()
            stale_records = self.search([('last_sync', '<', sync_start_time)])
            if stale_records:
                stale_records.unlink()
                _logger.info("Deleted %s stale driver records", len(stale_records))
            _logger.info("Driver sync completed successfully")
            return True
        except Exception as e:
            _logger.error("Driver sync failed: %s", str(e))
            return False