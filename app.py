import ANTS.app_lib
from ANTS.app_lib import get_data, get_list, get_title, check_etf
import dash
import dash_bootstrap_components as dbc
import dash_tvlwc
from dash_tvlwc.types import ColorType, SeriesType
from dash.dependencies import Input, Output, State
from dash import html, dcc
import dash_ag_grid as dag
import warnings
import subprocess
import os
from flask import request
from dotenv import load_dotenv
import urllib.parse

warnings.filterwarnings("ignore")
load_dotenv()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.title = 'ANTS Investment'

ticker_data = get_list('Ticker')
#index_data = get_list('ETF')
chart_data = []#get_data()
history_ticker = ''
history_column = ''

navbar = dbc.Navbar(
    dbc.Container([
        dbc.Row([
                    dbc.Col(html.Img(src=app.get_asset_url('logo.png'), height='17px'), className='m-0 p-0 align-middle'),   
                    dbc.Col(dbc.NavbarBrand('ANTS Investment'),className='sm mx-1 my-0 p-0 align-middle'),
                ],
                style={'font-family' : 'Times New Roman', },
                align="center",
                className="g-0",
                ),
        dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
        dbc.Collapse(
            dbc.Row(
                [
                    dbc.Col(dbc.Button('Predict', id='Predict', href="http://130.162.151.57:8050/", className='m-1 p-1 d-grid', size='sm', color='light', n_clicks=0, style={'min-width': '100px', 'width': '95%'}),),
                    dbc.Col(dbc.Button('Crpto', id='Crpto', href="http://152.70.242.126:8050/", className='m-1 p-1 d-grid', size='sm', color='light', n_clicks=0, style={'min-width': '100px', 'width': '95%'}),),
                ],
                style={'font-family' : 'Times New Roman', },
                className="g-0 ms-auto flex-nowrap mt-md-0",
                align="center",
            ),
            id="navbar-collapse",
            is_open=False,
            navbar=True,
        ),
    ]),
    color='dark',
    dark=True,
    fixed = 'top',
    class_name = 'm-0 p-0 align-middle',
    expand = 'sm'
)

def get_ticker_container() :
    ticker_container = dag.AgGrid(
        id='ticker-grid',
        rowData=ticker_data.to_dict('records'),
        columnDefs=[
            { 'field': 'ticker', 'headerName': 'Ticker', 'cellRenderer': 'markdown', 'width': 70, },
            { 'field': 'name', 'headerName': 'Name', 'width': 150, },
            { 'field': 'industry', 'headerName': 'Industry', 'width': 130, },
            #{ 'field': 'close', 'headerName': 'Price', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.0f')(params.value)"},},
            { 'field': 'per', 'headerName': 'PER', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'pbr', 'headerName': 'PBR', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'psr', 'headerName': 'PSR', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'ev_ebitda', 'headerName': 'EV/EBITDA', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            #{ 'field': 'dbr', 'headerName': 'DBR', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'perz', 'headerName': 'PER Z-Score', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'pbrz', 'headerName': 'PBR Z-Score', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'psrz', 'headerName': 'PSR Z-Score', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'ev_ebitdaz', 'headerName': 'EV/EBITDA Z-Score', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'pricez', 'headerName': 'Price Z-Score', 'type': 'numericColumn', 'width': 80, 'valueFormatter': {'function': "d3.format(',.1f')(params.value)"},},
            { 'field': 'marketcap', 'headerName': 'Market Cap', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.0f')(params.value)"},},
            { 'field': 'sales_growth', 'headerName': 'Sales Growth', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.0f')(params.value)"},},
            { 'field': 'op_growth', 'headerName': 'OP Growth', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.0f')(params.value)"},},
            { 'field': 'np_growth', 'headerName': 'NP Growth', 'type': 'numericColumn', 'width': 100, 'valueFormatter': {'function': "d3.format(',.0f')(params.value)"},},
        ],
        defaultColDef={'resizable': True, 'sortable': True, 'filter': True},
        #columnSize='sizeToFit',
        dashGridOptions = {'rowHeight': 35, 'headerHeight':35},
        style={'font-family' : 'Times New Roman', },
        getRowId='params.data.id',
    )
    return ticker_container

def get_chart_container() :
    chart_container = dash_tvlwc.Tvlwc(
            id='chart',
            seriesData=chart_data,
            seriesTypes=ANTS.app_lib.series_types,
            seriesOptions=ANTS.app_lib.series_options,
            width='100%',
            chartOptions=ANTS.app_lib.chart_options
    )
    return chart_container

# --- 페이지 레이아웃 정의 ---

# 1. 메인 대시보드 레이아웃
dashboard_layout = html.Div([
    html.Div(children=navbar),
    html.Br(),
    html.Br(),
    html.Div(className='table', id='ticker-container', children=get_ticker_container()),
    html.Div(id='ticker-name'),
    html.Div(id='chart-container', children=get_chart_container()), 
])

# 2. Notion에 임베드할 차트 전용 레이아웃
chart_embed_layout = html.Div([
    dash_tvlwc.Tvlwc(
        id='embedded-chart', # ID를 다르게 설정
        seriesTypes=ANTS.app_lib.series_types,
        seriesOptions=ANTS.app_lib.series_options,
        width='100%',
        height=400, # 임베드 환경에 맞는 높이 지정
        chartOptions=ANTS.app_lib.chart_options
    )
])

# --- URL 경로에 따라 다른 레이아웃을 보여주는 부분 ---
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/chart-embed':
        return chart_embed_layout
    else:
        return dashboard_layout

# --- 콜백 함수 정의 ---

# 1. 메인 대시보드 콜백
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open

@app.callback(
    Output('ticker-name', 'children', allow_duplicate=True),
    Output('chart', 'seriesData', allow_duplicate=True),
    Input('ticker-grid', 'cellClicked'),
    prevent_initial_call=True
)
def update_title(ticker_cell):
    #print(ticker_cell)
    if ticker_cell is not None and 'rowId' in ticker_cell and 'colId' in ticker_cell:
        ticker_cell_ticker = ticker_cell['rowId']
        ticker_cell_column = ticker_cell['colId']
    else : return dash.no_update
    if check_etf(ticker_cell_ticker) == True : return [html.H4(get_title(ticker_cell_ticker, 'pricez'), id='ticker-name', style={'font-family' : 'Nanum Myeongjo, serif'})], get_data(ticker_cell_ticker, 'ETF')
    else : return [html.H4(get_title(ticker_cell_ticker, ticker_cell_column), id='ticker-name', style={'font-family' : 'Nanum Myeongjo, serif'})], get_data(ticker_cell_ticker, ticker_cell_column)
    #return get_data(ticker_cell_ticker, ticker_cell_column)

# 2. 임베드된 차트용 콜백
@app.callback(
    Output('embedded-chart', 'seriesData'),
    Input('url', 'search')
)
def update_embedded_chart(search):
    if not search:
        return dash.no_update
    
    # URL의 쿼리 파라미터 파싱 (예: ?ticker=005930&column_id=perz)
    params = urllib.parse.parse_qs(search.lstrip('?'))
    ticker = params.get('ticker', [None])[0]
    column_id = params.get('column_id', [None])[0]

    if ticker and column_id:
        return get_data(ticker, column_id)
    
    return []

@server.route('/run-manual-update', methods=['POST'])
def run_manual_update():
    """
    API endpoint to trigger the ants_manual.py script.
    Requires a secret key in the JSON body for authorization.
    """
    secret_key = os.getenv('ANTS_API_KEY')

    # Get JSON data from the request
    data = request.get_json()
    if not data:
        return {"status": "error", "message": "Invalid request. JSON body required."}, 400

    auth_key = data.get('api_key')
    
    if not secret_key or auth_key != secret_key:
        return {"status": "error", "message": "Unauthorized"}, 401

    try:
        # Run ants_manual.py as a non-blocking background process
        script_path = '/home/ants/ants_manual.py'
        process = subprocess.Popen(['python3', script_path])

        # Return a 202 Accepted response immediately
        return {"status": "success", "message": f"Manual update process started with PID: {process.pid}"}, 202
    except FileNotFoundError:
        return {"status": "error", "message": f"Script not found at {script_path}"}, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='8050', debug=False)
