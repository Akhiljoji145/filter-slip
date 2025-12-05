# TODO List for Implementing Sessions in Voters App

- [x] Modify `voters_app.py` to store booth_no in session in `select_booth` route
- [x] Modify `get_details` route in `voters_app.py` to store selections in session and use session data for booth_no
- [x] Update `templates/index.html` to properly display the session-based selections queue
- [ ] Test the app to ensure sessions work and no interference between users
- [ ] Add session clearing functionality if needed
