from odoo import models, fields, api
import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProfilePassenger(models.Model):
    _name = 'profile.passenger'
    _description = 'Passenger Profile'
    _rec_name = 'phone_number'
    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'External ID must be unique.'),
    ]

    external_id = fields.Integer(string='External ID', required=True, index=True)
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    phone_number = fields.Char(string='Phone Number', required=True)
    email = fields.Char(string='Email')
    rides = fields.Char(string='Rides')  # Stored as JSON string for simplicity
    favourites = fields.Char(string='Favourites')  # Stored as JSON string
    last_sync = fields.Datetime(string='Last Synced', readonly=True)

    @api.model
    def fetch_passenger_list(self):
        """Fetch and return the list of passengers from the API."""
        api_url = 'http://147.93.52.105:9082/api/v1/profile/passenger'
        try:
            _logger.info("Fetching passenger list from API: %s", api_url)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=10)
            _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            
            if response.status_code != 200:
                _logger.error("Failed to fetch passenger list: %s (Status: %s)", response.text, response.status_code)
                raise UserError(f"Failed to fetch passenger list: {response.text} (Status: {response.status_code})")
            
            passengers = response.json()
            if not isinstance(passengers, list):
                _logger.error("Invalid API response format: Expected list, got %s", type(passengers).__name__)
                raise UserError(f"Invalid API response format: Expected list, got {type(passengers).__name__}")

            # Update or create records
            passenger_ids = []
            for passenger in passengers:
                external_id = passenger.get('id', 0)
                if not external_id:
                    _logger.warning("Skipping passenger with missing id: %s", passenger)
                    continue
                
                passenger_data = {
                    'external_id': external_id,
                    'first_name': passenger.get('firstName'),
                    'last_name': passenger.get('lastName'),
                    'phone_number': passenger.get('phoneNumber', ''),
                    'email': passenger.get('email'),
                    'rides': str(passenger.get('rides', [])),
                    'favourites': str(passenger.get('favourites', [])),
                    'last_sync': fields.Datetime.now(),
                }
                
                existing = self.search([('external_id', '=', external_id)], limit=1)
                if existing:
                    existing.write(passenger_data)
                    passenger_ids.append(existing.id)
                    _logger.debug("Updated passenger with external_id %s", external_id)
                else:
                    new_record = self.create(passenger_data)
                    passenger_ids.append(new_record.id)
                    _logger.debug("Created passenger with external_id %s", external_id)

            _logger.info("Synced %s passenger records", len(passenger_ids))
            return self.browse(passenger_ids)
        except requests.RequestException as e:
            _logger.error("API request failed for passenger list: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def fetch_passenger_details(self, external_id):
        """Fetch details of a specific passenger by ID."""
        api_url = f'http://147.93.52.105:9082/api/v1/profile/passenger/{external_id}'
        try:
            _logger.info("Fetching passenger details from API: %s", api_url)
            response = requests.get(api_url, headers={'Content-Type': 'application/json'}, timeout=10)
            _logger.info("API GET %s response: %s (Status: %s)", api_url, response.text, response.status_code)
            
            if response.status_code == 404:
                _logger.warning("Passenger not found for external_id %s", external_id)
                raise UserError("Passenger not found")
            if response.status_code != 200:
                _logger.error("Failed to fetch passenger details: %s (Status: %s)", response.text, response.status_code)
                raise UserError(f"Failed to fetch passenger details: {response.text} (Status: {response.status_code})")
            
            passenger = response.json()
            if not isinstance(passenger, dict):
                _logger.error("Invalid API response format: Expected dict, got %s", type(passenger).__name__)
                raise UserError(f"Invalid API response format: Expected dict, got {type(passenger).__name__}")

            passenger_data = {
                'external_id': passenger.get('id', 0),
                'first_name': passenger.get('firstName'),
                'last_name': passenger.get('lastName'),
                'phone_number': passenger.get('phoneNumber', ''),
                'email': passenger.get('email'),
                'rides': str(passenger.get('rides', [])),
                'favourites': str(passenger.get('favourites', [])),
                'last_sync': fields.Datetime.now(),
            }

            existing = self.search([('external_id', '=', passenger.get('id', 0))], limit=1)
            if existing:
                existing.write(passenger_data)
                passenger_id = existing.id
                _logger.debug("Updated passenger with external_id %s", passenger.get('id'))
            else:
                passenger_record = self.create(passenger_data)
                passenger_id = passenger_record.id
                _logger.debug("Created passenger with external_id %s", passenger.get('id'))

            _logger.info("Fetched and processed passenger record with external_id %s", passenger.get('id'))
            return passenger_id
        except requests.RequestException as e:
            _logger.error("API request failed for passenger details: %s", str(e))
            raise UserError(f"API request failed: {str(e)}")
        except ValueError as e:
            _logger.error("Failed to parse API response: %s", str(e))
            raise UserError(f"Invalid API response: {str(e)}")

    @api.model
    def sync_passengers(self):
        """Sync passenger data from API, used by cron job."""
        try:
            _logger.info("Starting passenger data sync via cron")
            passengers = self.fetch_passenger_list()
            # Delete stale records (older than last sync)
            stale_records = self.search([('last_sync', '<', fields.Datetime.now())])
            if stale_records:
                stale_records.unlink()
                _logger.info("Deleted %s stale passenger records", len(stale_records))
            _logger.info("Passenger sync completed successfully")
            return True
        except Exception as e:
            _logger.error("Passenger sync failed: %s", str(e))
            return False
