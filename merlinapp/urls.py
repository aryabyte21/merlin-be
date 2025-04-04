from django.urls import path
from .views import (
    redwatch_api, smartkargo_api, merge_data, update_received,
    mawb_suggestions, populate_dummy_data, trolley_login,
    flight_suggestions, mawb_by_flight, update_bt_number
)

urlpatterns = [
    path('redwatch/', redwatch_api, name='redwatch_api'),
    path('smartkargo/', smartkargo_api, name='smartkargo_api'),
    path('merge/', merge_data, name='merge_data'),
    path('update/', update_received, name='update_received'),
    path('mawb-suggestions/', mawb_suggestions, name='mawb_suggestions'),
    path('populate/', populate_dummy_data, name='populate_dummy_data'),
    path('trolley-login/', trolley_login, name='trolley_login'),
    path('flight-suggestions/', flight_suggestions, name='flight_suggestions'),
    path('mawb-by-flight/', mawb_by_flight, name='mawb_by_flight'),
    path('update-bt/', update_bt_number, name='update_bt_number'),
]
