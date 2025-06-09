from odoo import http
from odoo.http import request
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProfileManagementController(http.Controller):

    @http.route('/profiles/passengers', type='http', auth='user', methods=['GET'], website=True)
    def passenger_list(self, **kwargs):
        try:
            passengers = request.env['profile.passenger'].search([])
            if not passengers:
                _logger.info("No passenger data found, fetching from API")
                passengers = request.env['profile.passenger'].fetch_passenger_list()
            return request.render('profiles_management.passenger_list_template', {
                'passengers': passengers,
            })
        except Exception as e:
            _logger.error("Error fetching passenger list: %s", str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/passenger/<int:passenger_id>', type='http', auth='user', methods=['GET'], website=True)
    def passenger_details(self, passenger_id, **kwargs):
        try:
            passenger = request.env['profile.passenger'].search([('external_id', '=', passenger_id)], limit=1)
            if not passenger:
                _logger.info("Passenger with external_id %s not found, fetching from API", passenger_id)
                passenger_record_id = request.env['profile.passenger'].fetch_passenger_details(passenger_id)
                passenger = request.env['profile.passenger'].browse(passenger_record_id)
            if not passenger.exists():
                return request.render('profiles_management.error_template', {
                    'error': 'Passenger not found',
                })
            return request.render('profiles_management.passenger_details_template', {
                'passenger': passenger,
            })
        except Exception as e:
            _logger.error("Error fetching passenger details for ID %s: %s", passenger_id, str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/drivers', type='http', auth='user', methods=['GET'], website=True)
    def driver_list(self, **kwargs):
        try:
            first_name = kwargs.get('first_name')
            last_name = kwargs.get('last_name')
            if first_name or last_name:
                _logger.info("Filtering drivers with first_name: %s, last_name: %s", first_name, last_name)
                drivers = request.env['profile.driver'].fetch_filtered_drivers(first_name, last_name)
            else:
                drivers = request.env['profile.driver'].search([])
                if not drivers:
                    _logger.info("No drivers found, fetching from API")
                    drivers = request.env['profile.driver'].fetch_driver_list()
            return request.render('profiles_management.driver_list_template', {
                'drivers': drivers,
                'kwargs': kwargs,  # Pass kwargs to retain form input values
            })
        except Exception as e:
            _logger.error("Error fetching driver list: %s", str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/drivers/search', type='json', auth='user', methods=['POST'])
    def driver_search(self, search_term, field='first_name'):
        try:
            _logger.info("UI search for term: %s on field: %s", search_term, field)
            first_name = search_term if field == 'first_name' else None
            last_name = search_term if field == 'last_name' else None
            drivers = request.env['profile.driver'].fetch_filtered_drivers(first_name, last_name)
            return {
                'records': [{
                    'id': driver.id,
                    'external_id': driver.external_id,
                    'first_name': driver.first_name or '',
                    'last_name': driver.last_name or '',
                    'phone_number': driver.phone_number or '',
                    'driver_number': driver.driver_number or '',
                    'username': driver.username or '',
                    'last_sync': driver.last_sync and driver.last_sync.strftime('%Y-%m-%d %H:%M:%S') or ''
                } for driver in drivers],
                'length': len(drivers)
            }
        except Exception as e:
            _logger.error("Error in UI search for term %s: %s", search_term, str(e))
            raise UserError(str(e))

    @http.route('/profiles/driver/<int:driver_id>', type='http', auth='user', methods=['GET'], website=True)
    def driver_details(self, driver_id, **kwargs):
        try:
            driver = request.env['profile.driver'].search([('external_id', '=', driver_id)], limit=1)
            if not driver:
                _logger.info("Driver with external_id %s not found, fetching from API", driver_id)
                driver_record_id = request.env['profile.driver'].fetch_driver_details(driver_id)
                driver = request.env['profile.driver'].browse(driver_record_id)
            if not driver.exists():
                return request.render('profiles_management.error_template', {
                    'error': 'Driver not found',
                })
            return request.render('profiles_management.driver_details_template', {
                'driver': driver,
            })
        except Exception as e:
            _logger.error("Error fetching driver details for ID %s: %s", driver_id, str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/driver/new', type='http', auth='user', methods=['GET'], website=True)
    def driver_create_form(self, **kwargs):
        return request.render('profiles_management.driver_create_form_template')

    @http.route('/profiles/driver/create', type='http', auth='user', methods=['POST'], website=True)
    def driver_create_submit(self, **kwargs):
        try:
            values = {
                'first_name': kwargs.get('first_name'),
                'last_name': kwargs.get('last_name'),
                'phone_number': kwargs.get('phone_number'),
                'driver_number': kwargs.get('driver_number'),
                'rides': kwargs.get('rides', '[]'),
                'username': kwargs.get('username'),
                'password': kwargs.get('password'),
            }
            required_fields = ['first_name', 'last_name', 'phone_number', 'driver_number', 'username', 'password']
            missing = [field for field in required_fields if not values[field]]
            if missing:
                raise UserError(f"Missing required fields: {', '.join(missing)}")
            driver = request.env['profile.driver'].create(values)
            return request.redirect('/profiles/drivers')
        except Exception as e:
            _logger.error("Error creating driver: %s", str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/driver/edit/<int:driver_id>', type='http', auth='user', methods=['GET'], website=True)
    def driver_edit_form(self, driver_id, **kwargs):
        try:
            driver = request.env['profile.driver'].browse(driver_id)
            if not driver.exists():
                return request.render('profiles_management.error_template', {
                    'error': 'Driver not found',
                })
            return request.render('profiles_management.driver_edit_form_template', {
                'driver': driver,
            })
        except Exception as e:
            _logger.error("Error loading driver edit form for ID %s: %s", driver_id, str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/driver/edit/<int:driver_id>', type='http', auth='user', methods=['POST'], website=True)
    def driver_edit_submit(self, driver_id, **kwargs):
        try:
            driver = request.env['profile.driver'].browse(driver_id)
            if not driver.exists():
                raise UserError("Driver not found")
            values = {
                'first_name': kwargs.get('first_name'),
                'last_name': kwargs.get('last_name'),
                'phone_number': kwargs.get('phone_number'),
                'driver_number': kwargs.get('driver_number'),
                'rides': kwargs.get('rides', '[]'),
                'username': kwargs.get('username'),
            }
            if kwargs.get('password'):
                values['password'] = kwargs.get('password')
            required_fields = ['first_name', 'last_name', 'phone_number', 'driver_number', 'username']
            missing = [field for field in required_fields if not values[field]]
            if missing:
                raise UserError(f"Missing required fields: {', '.join(missing)}")
            existing = request.env['profile.driver'].search([
                ('phone_number', '=', values['phone_number']),
                ('username', '=', values['username']),
                ('id', '!=', driver.id),
            ], limit=1)
            if existing:
                raise UserError(f"Driver with phone number {values['phone_number']} and username {values['username']} already exists (external ID: {existing.external_id}).")
            _logger.info("Submitting driver update for driver_id %s with values: %s", driver_id, values)
            request.env['profile.driver'].update_driver(driver_id, values)
            return request.redirect('/profiles/drivers')
        except Exception as e:
            _logger.error("Error updating driver for ID %s: %s", driver_id, str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })

    @http.route('/profiles/driver/delete/<int:driver_id>', type='http', auth='user', methods=['GET'], website=True)
    def driver_delete(self, driver_id, **kwargs):
        try:
            driver = request.env['profile.driver'].search([('external_id', '=', driver_id)], limit=1)
            if not driver.exists():
                return request.render('profiles_management.error_template', {
                    'error': 'Driver not found',
                })
            driver.unlink()
            return request.redirect('/profiles/drivers')
        except Exception as e:
            _logger.error("Error deleting driver for ID %s: %s", driver_id, str(e))
            return request.render('profiles_management.error_template', {
                'error': str(e),
            })