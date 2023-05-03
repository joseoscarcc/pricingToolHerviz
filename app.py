import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
from sqlalchemy import Table, create_engine
from sqlalchemy.sql import select
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import warnings
import os
from flask_login import login_user, logout_user, current_user, LoginManager, UserMixin
import configparser
import getPrices
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


TGSites = getPrices.TGSites
wt01 = getPrices.worktable
tableGraphs = getPrices.preciosHist
costos01 = getPrices.costos01
costos02 = getPrices.costos02

descargarTabla = pd.DataFrame()

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

warnings.filterwarnings("ignore")
conn_string = os.getenv('urlDB')
engine = create_engine(conn_string)
db = SQLAlchemy()
config = configparser.ConfigParser()
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True, nullable = False)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))
    type = db.Column(db.String(15))
    project = db.Column(db.String(15))
Users_tbl = Table('users', Users.metadata)
app = dash.Dash(__name__, external_stylesheets=external_stylesheets) #app = Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server
app.config.suppress_callback_exceptions = True
# config
server.config.update(
    SECRET_KEY=os.urandom(12),
    SQLALCHEMY_DATABASE_URI=conn_string,
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)
db.init_app(server)
# Setup the LoginManager for the server
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'
#User as base
# Create User class with UserMixin
class Users(UserMixin, Users):
    pass
#variables
mapbox_access_token = os.getenv('mapbox_access_token')

def generate_table(dataframe, max_rows=20):
    return html.Table(
        # Header
        [html.Tr([html.Th(col) for col in dataframe.columns])] +

        # Body
        [html.Tr([
            html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
        ]) for i in range(min(len(dataframe), max_rows))]
    ) 

def generate_map(dataframe,citylat,citylon):
    fig = go.Figure(go.Scattermapbox(
            lon = dataframe['x'],
            lat = dataframe['y'],
            text = dataframe['text'],
            mode = 'markers'
            ))

    fig.update_layout(
            title = 'Mapa de Precios',
            autosize=True,
            hovermode='closest',
            mapbox=dict(
            accesstoken=mapbox_access_token,
            bearing=0,
            center=dict(
                lat=citylat,
                lon=citylon
            ),
            pitch=0,
            zoom=10
    ),
        )
    return html.Div([
    dcc.Graph(figure=fig)
    ])

def generate_graphs(dataframe):
    df = dataframe.pivot_table(values='prices', index=['date','marca'], aggfunc=[np.mean])
    df.columns = df.columns.droplevel(0)
    df = df.reset_index()
    df = df.round(2)
    fig = px.line(df, 
        x="date",y='prices', color='marca',title='Precios por Marca')
    return html.Div([
    dcc.Graph(figure=fig)
    ])

def generate_costs(tc01, tc02):
    regular_fig = go.Figure(go.Indicator(
        mode = "number+delta",
        value = tc01['precio_tar'][tc01['producto']=='regular'].item(),
        title = {"text": "Regular<br><span style='font-size:0.8em;color:gray'>Precio x Litro</span><br><span style='font-size:0.8em;color:gray'>comparativo vs dia anterior</span>"},
        delta = {'reference': tc02['precio_tar'][tc02['producto']=='regular'].item(), 'relative': True}
    ))
    
    premium_fig = go.Figure(go.Indicator(
        mode = "number+delta",
        value = tc01['precio_tar'][tc01['producto']=='premium'].item(),
        title = {"text": "Premium<br><span style='font-size:0.8em;color:gray'>Precio x Litro</span><br><span style='font-size:0.8em;color:gray'>comparativo vs dia anterior</span>"},
        delta = {'reference': tc02['precio_tar'][tc02['producto']=='premium'].item(), 'relative': True}
    ))
    
    diesel_fig = go.Figure(go.Indicator(
        mode = "number+delta",
        value = tc01['precio_tar'][tc01['producto']=='diesel'].item(),
        title = {"text": "Diesel<br><span style='font-size:0.8em;color:gray'>Precio x Litro</span><br><span style='font-size:0.8em;color:gray'>comparativo vs dia anterior</span>"},
        delta = {'reference': tc02['precio_tar'][tc02['producto']=='diesel'].item(), 'relative': True}
    ))
    
    return html.Div([
        dcc.Graph(figure=regular_fig, style={'display': 'inline-block', 'width': '30%'}),
        dcc.Graph(figure=premium_fig, style={'display': 'inline-block', 'width': '30%'}),
        dcc.Graph(figure=diesel_fig, style={'display': 'inline-block', 'width': '30%'}),
    ], style={'text-align': 'center'})

tab1 = html.Div([
            html.H4(children='Estaciones de Servicio JOJUMA BI Pricing Tool DEMO'),
                dcc.Checklist(
                    id='mychecklist',
                    options = ['regular', 'premium', 'diesel'],
                    value = ['regular'],
                    inline=True
                ),
                dcc.Dropdown(id='dropdown', options=[
                    {'label': i, 'value': i} for i in TGSites.cre_id.unique()
                ], multi=True, placeholder='Filter by Permiso CRE...'),
                html.Div(id='table-container'),
                html.Button("Download CSV", id="btn_csv"),
                dcc.Download(id="download-dataframe-csv"),
            ])

tab2 = html.Div([
            html.H4(children='Mapa de Estaciones de Servicio'),
                dcc.Dropdown(['Tijuana', 'Hermosillo', 'Torreon', 'Merida', 'Puebla'], 'Tijuana', id='dropdownMapa'),
                dcc.RadioItems(
                    ['regular', 'premium','diesel'], 'regular',
                    id='productType',
                    inline=True
                ),
                html.Div(id='dd-output-container')
])    

tab3 = html.Div([
            html.H4(children='Gráficas precios últimos 30 días'),
                dcc.Dropdown(id='dropdownGraphs', options=[
                    {'label': i, 'value': i} for i in TGSites.cre_id.unique()
                ], multi=True, placeholder='Filter by Permiso CRE...'),
                dcc.RadioItems(
                    ['regular', 'premium','diesel'], 'regular',
                    id='productTypeGraphs',
                    inline=True
                ),
                html.Div(id='container_graphs')
])

tab4 = html.Div([
            html.H4(children='COSTOS PEMEX'),
                dcc.Dropdown(id='dropdowncostos', options=[
                    {'label': i, 'value': i} for i in costos01.terminal.unique()
                ], multi=True, placeholder='Escoge la terminal mas cercana...'),
                html.Div(id='container_costs')
])
# create = html.Div([ html.H1('Create User Account')
#         , dcc.Location(id='create_user', refresh=True)
#         , dcc.Input(id="username"
#             , type="text"
#             , placeholder="user name"
#             , maxLength =15)
#         , dcc.Input(id="password"
#             , type="password"
#             , placeholder="password")
#         , dcc.Input(id="email"
#             , type="email"
#             , placeholder="email"
#             , maxLength = 50)
#         , html.Button('Create User', id='submit-val', n_clicks=0)
#         , html.Div(id='container-button-basic')
#     ])#end div
image_path = 'assets/jojuma.png'

login =  html.Div([dcc.Location(id='url_login', refresh=True)
            , html.Img(src=image_path)
            , html.H1('Bienvenido a Jojuma BI - Fuel Pricing Tool')
            , html.H2('''Ingresa tu usuario y contraseña''', id='h1')
            , dcc.Input(placeholder='Usuario',
                    type='text',
                    id='uname-box')
            , dcc.Input(placeholder='Contraseña',
                    type='password',
                    id='pwd-box')
            , html.Button(children='Ingresa',
                    n_clicks=0,
                    type='submit',
                    id='login-button')
            , html.Div(children='', id='output-state')
        ]) #end div
# success = html.Div([dcc.Location(id='url_login_success', refresh=True)
#             , html.Div([html.H2('Login successful.')
#                     , html.Br()
#                     , html.P('Select a Dataset')
#                     , dcc.Link('Data', href = '/data')
#                 ]) #end div
#             , html.Div([html.Br()
#                     , html.Button(id='back-button', children='Go back', n_clicks=0)
#                 ]) #end div
#         ]) #end div
data = html.Div([
    html.H1('JOJUMA BI Pricing Tool - DEMO'),
    dcc.Tabs(id="tabs-example", value='tab-1', children=[
        dcc.Tab(id="tab-1", label='Precios', value='tab-1'),
        dcc.Tab(id="tab-2", label='Mapa', value='tab-2'),
        dcc.Tab(id="tab-3", label='Grafica', value='tab-3'),
        dcc.Tab(id="tab-4", label='Costos', value='tab-4'),
    ]),
    html.Div(id='tabs-content',
             children = [tab1,tab2,tab3,tab4]),
    
    # html.Div([dcc.Dropdown(
    #                 id='dropdown',
    #                 options=[{'label': i, 'value': i} for i in ['Day 1', 'Day 2']],
    #                 value='Day 1')
    #             , html.Br()
    #             , html.Div([dcc.Graph(id='graph')])
    #         ]) #end div
     html.Div([html.Br()
             , html.Button(id='back-button', children='Go back', n_clicks=0)
              ]) #end div
])
failed = html.Div([ dcc.Location(id='url_login_df', refresh=True)
            , html.Div([html.H2('Log in Failed. Please try again.')
                    , html.Br()
                    , html.Div([login])
                    , html.Br()
                    , html.Button(id='back-button', children='Go back', n_clicks=0)
                ]) #end div
        ]) #end div
logout = html.Div([dcc.Location(id='logout', refresh=True)
        , html.Br()
        , html.Div(html.H2('You have been logged out - Please login'))
        , html.Br()
        , html.Div([login])
        , html.Button(id='back-button', children='Go back', n_clicks=0)
    ])#end div
app.layout= html.Div([
            html.Div(id='page-content', className='content')
            ,  dcc.Location(id='url', refresh=False)
        ])
# callback to reload the user object
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))
@app.callback(
    Output('page-content', 'children')
    , [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/':
        return login
    elif pathname == '/login':
        return login
    # elif pathname == '/success':
    #     if current_user.is_authenticated:
    #         return success
    #     else:
    #         return failed
    elif pathname =='/data':
        if current_user.is_authenticated:
            return data
    elif pathname == '/logout':
        if current_user.is_authenticated:
            logout_user()
            return logout
        else:
            return logout
    else:
        return '404'
@app.callback(Output('tabs-content', 'children'),
             [Input('tabs-example', 'value')])
def render_content(tab):
    if tab == 'tab-1':
        return tab1
    elif tab == 'tab-2':
        return tab2
    elif tab == 'tab-3':
        return tab3
    elif tab == 'tab-4':
        return tab4
@app.callback(
    Output('table-container', 'children'),
    Input('dropdown', 'value'),
    Input('mychecklist','value'))
def display_table(dropdown, mychecklist):
    global table
    if dropdown is None:
        placeIDTG = TGSites['place_id'].to_list()
    else:
        placeIDTG = TGSites['place_id'][TGSites.cre_id.str.contains('|'.join(dropdown))]
    dff = wt01
    dff = dff[dff['compite_a'].isin(placeIDTG)]
    table = pd.pivot_table(dff[['cre_id','marca','prices','dif','product']], values=['prices','dif'], index=['cre_id', 'marca'],
                    columns=['product'], aggfunc=np.mean, fill_value="-")
    #coculs = ['cre_id','Marca'] + mychecklist
    table = table.reindex(columns=['prices','dif'], level=0)
    table = table.reindex(columns=mychecklist, level=1)
    table.columns = table.columns.map('|'.join).str.strip('|')
    table = table.round(2)
    table = table.reset_index()
    #newTable = pd.concat([table[table["marca"] == 'TOTAL GAS'],table[table['marca'] != 'TOTAL GAS']])
    return generate_table(table)

@app.callback(
    Output('dd-output-container', 'children'),
    Input('dropdownMapa', 'value'),
    Input('productType','value'))
def make_map(dropdownMapa, productType):
   
    df0 = wt01[wt01['product']==productType] 
    placeIDTG = TGSites['place_id'][TGSites['Municipio']==dropdownMapa]
    df = df0[df0['compite_a'].isin(placeIDTG)]
    df['text'] = df['marca'] + ' ' + df['cre_id'] + ', Precio: ' + df['prices'].astype(str)

    if dropdownMapa == 'Hermosillo':
        citylat = 29.06933
        citylon = -110.9706
    elif dropdownMapa == "Merida":
        citylat = 20.94868
        citylon = -89.64977
    elif dropdownMapa == "Puebla":
        citylat = 19.0257
        citylon = -98.20509
    elif dropdownMapa == "Torreon":
        citylat = 25.54993
        citylon = -103.4232
    elif dropdownMapa == "Tijuana":
        citylat = 32.51887
        citylon = -117.0121

    return generate_map(df,citylat,citylon)

@app.callback(
    Output('container_graphs', 'children'),
    Input('dropdownGraphs', 'value'),
    Input('productTypeGraphs','value'))
def display_table(dropdownGraphs, productTypeGraphs):

    if dropdownGraphs is None:
        placeIDTG = TGSites['place_id'][TGSites.cre_id.str.contains('PL/640/EXP/ES/2015')]
    else:
        placeIDTG = TGSites['place_id'][TGSites.cre_id.str.contains('|'.join(dropdownGraphs))]

    graphTable = tableGraphs[tableGraphs['compite_a'].isin(placeIDTG)]
    graphTable = graphTable[graphTable['product']==productTypeGraphs] 
    return generate_graphs(graphTable)

@app.callback(
    Output('container_costs', 'children'),
    Input('dropdowncostos', 'value'))
def display_costs(dropdownCosts):

    if dropdownCosts is None:
        costoTerminal = costos01[costos01.terminal.str.contains('AZCAPOTZALCO')]
    else:
        costoTerminal = costos01[costos01.terminal.str.contains('|'.join(dropdownCosts))]

    if dropdownCosts is None:
        costoTerminal02 = costos02[costos02.terminal.str.contains('AZCAPOTZALCO')]
    else:
        costoTerminal02 = costos02[costos02.terminal.str.contains('|'.join(dropdownCosts))]
      
    return generate_costs(costoTerminal,costoTerminal02)

@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn_csv", "n_clicks"),
    prevent_initial_call=True,
)
def func(n_clicks):
    return dcc.send_data_frame(table.to_csv, "tabla.csv")


@app.callback(
    Output('url_login', 'pathname')
    , [Input('login-button', 'n_clicks')]
    , [State('uname-box', 'value'), State('pwd-box', 'value')])
def successful(n_clicks, input1, input2):
    user = Users.query.filter_by(username=input1).first()
    if user:
        if user.project == "herviz" or user.project == "jojuma":
            if check_password_hash(user.password, input2):
                login_user(user)
                return '/data'
            else:
                pass
        else:
            pass
    else:
        pass
@app.callback(
    Output('output-state', 'children')
    , [Input('login-button', 'n_clicks')]
    , [State('uname-box', 'value'), State('pwd-box', 'value')])
def update_output(n_clicks, input1, input2):
    if n_clicks > 0:
        user = Users.query.filter_by(username=input1).first()
        if user:
            if check_password_hash(user.password, input2):
                return ''
            else:
                return 'Incorrect username or password'
        else:
            return 'Incorrect username or password'
    else:
        return ''
@app.callback(
    Output('url_login_success', 'pathname')
    , [Input('back-button', 'n_clicks')])
def logout_dashboard(n_clicks):
    if n_clicks > 0:
        return '/'
    else:
        return '/logout'
@app.callback(
    Output('url_login_df', 'pathname')
    , [Input('back-button', 'n_clicks')])
def logout_dashboard(n_clicks):
    if n_clicks > 0:
        return '/'
    else:
        return '/logout'
# Create callbacks
@app.callback(
    Output('url_logout', 'pathname')
    , [Input('back-button', 'n_clicks')])
def logout_dashboard(n_clicks):
    if n_clicks > 0:
        return '/'
    else:
        return '/logout'
if __name__ == '__main__':
    app.run_server(debug=True)
