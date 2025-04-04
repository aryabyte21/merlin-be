from django.apps import AppConfig


class MerlinappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'merlinapp'
    
    def ready(self):
        """
        This method is called when the application is ready.
        We'll use it to initialize our Google Sheet with data if needed.
        """
        # Import here to avoid circular imports
        from .utils import populate_sheet_with_dummy_data
        
        # Populate the sheet with dummy data
        # Only in non-testing environments
        import sys
        if 'runserver' in sys.argv:
            populate_sheet_with_dummy_data()
