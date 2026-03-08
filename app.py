import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# 1. Cargamos la lista de invitados (config.yaml)
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# 2. Creamos el portero del muro de entrada
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# 3. Dibujamos el formulario de entrada en la web
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # SI LA CONTRASEÑA ES CORRECTA, ENTRA AQUÍ
    authenticator.logout('Cerrar sesión', 'sidebar')
    st.write(f'# Bienvenido, Director {name}')
    st.success("Acceso concedido a los Protocolos MSK")
    
    # Aquí iría el resto de tu lógica clínica (F3, PC-03, etc.)
    
elif authentication_status == False:
    st.error('Usuario o contraseña incorrectos')
elif authentication_status == None:
    st.warning('Por favor, introduce tu usuario y contraseña')