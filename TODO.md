# TODO List for Implementing Sessions in Voters App

- [x] Modify `voters_app.py` to store booth_no in session in `select_booth` route
- [x] Modify `get_details` route in `voters_app.py` to store selections in session and use session data for booth_no
- [x] Update `templates/index.html` to properly display the session-based selections queue
- [ ] Test the app to ensure sessions work and no interference between users
- [ ] Add session clearing functionality if needed

# TODO List for Implementing Database Comparison Feature

- [ ] Add helper functions in voters_app.py for getting unique house_nos and house_names from both databases
- [ ] Add /comparison route in voters_app.py to render the comparison form
- [ ] Add /compare_results route in voters_app.py to handle form submission and render results
- [ ] Create templates/comparison.html for the comparison form
- [ ] Create templates/compare_results.html for displaying comparison results
- [ ] Add "Compare Databases" link in templates/index.html
- [ ] Test the new comparison functionality

# Breakdown of Approved Plan Steps
- [ ] Add get_unique_house_names_both() and get_unique_house_nos_both() functions in voters_app.py
- [ ] Add /comparison route in voters_app.py
- [ ] Add /compare_results route in voters_app.py
- [ ] Create templates/comparison.html
- [ ] Create templates/compare_results.html
- [ ] Update templates/index.html with "Compare Databases" link
- [ ] Test the implementation
- [ ] Update TODO.md to mark completed steps
