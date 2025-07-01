"""
Module pour l'interface utilisateur web basée sur Dash.
"""
from typing import Dict, List, Optional, Union
import logging
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
import time
import threading
import requests

import dash
from dash import dcc, html, callback, Input, Output, State, ALL, MATCH, Output
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

import config
from data_fetcher.fetcher import DataFetcher
from indicator_calculator.indicators import IndicatorCalculator
from signal_detector.detector import SignalDetector
from backtest.backtester import Backtester
from discord_notifier.notifier import DiscordNotifier
from monitoring_service import MonitoringService
from watchlist.manager import WatchlistManager

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

# Ajouter le répertoire parent au chemin pour pouvoir importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Dashboard:
    """
    Classe principale pour le tableau de bord de l'application TvBin.
    """
    
    def keep_alive(self):
        """
        Ping l'URL publique de l'app toutes les 14 minutes pour éviter la mise en veille.
        """
        while True:
            try:
                # Remplace cette URL par l'URL publique de ton app sur Render/Railway
                requests.get("https://ton-app.render.com/", timeout=10)
            except Exception as e:
                logger.warning(f"Keep-alive failed: {e}")
            time.sleep(14 * 60)  # 14 minutes

    def __init__(self):
        """Initialise le tableau de bord avec les composants nécessaires."""
        # Initialiser les composants
        self.data_fetcher = DataFetcher()
        self.indicator_calculator = IndicatorCalculator()
        self.signal_detector = SignalDetector(
            data_fetcher=self.data_fetcher,
            indicator_calculator=self.indicator_calculator
        )
        self.backtester = Backtester(
            data_fetcher=self.data_fetcher,
            indicator_calculator=self.indicator_calculator
        )
        self.discord_notifier = DiscordNotifier()
        self.monitoring_service = MonitoringService(
            signal_detector=self.signal_detector,
            discord_notifier=self.discord_notifier
        )
        
        # Initialiser l'application Dash
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.DARKLY],
            suppress_callback_exceptions=True,
            title=config.APP_CONFIG["title"]
        )
        
        # Lancer le thread keep-alive pour éviter la mise en veille
        threading.Thread(target=self.keep_alive, daemon=True).start()
        
        # Précharger les données des cryptos principales
        self._preload_data()
        
        # Mise à jour automatique des tickers au démarrage
        self.tickers_added, self.tickers_removed = self._update_cmc_tickers()
        
        # Ajouter du CSS personnalisé pour améliorer le contraste
        self.app.index_string = '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                {%favicon%}
                {%css%}
                <style>
                    /* Améliorer le contraste des listes déroulantes */
                    .Select-control, .Select-menu-outer {
                        background-color: #2c3e50 !important;
                        color: white !important;
                    }
                    .Select-value-label, .Select-option {
                        color: white !important;
                    }
                    .Select-value, .Select-placeholder {
                        color: white !important;
                    }
                    /* Améliorer le contraste des inputs */
                    .form-control {
                        background-color: #2c3e50 !important;
                        color: white !important;
                        border: 1px solid #3498db !important;
                    }
                    /* Améliorer la visibilité des chandeliers */
                    .js-plotly-plot .plotly .candlestick {
                        opacity: 0.9 !important;
                    }
                    /* Améliorer la visibilité des onglets */
                    .nav-tabs {
                        border-bottom: 1px solid #3498db !important;
                    }
                    .nav-tabs .nav-link.active {
                        background-color: #3498db !important;
                        color: white !important;
                    }
                    /* Style pour les alertes */
                    .alert-crypto {
                        background-color: #e74c3c !important;
                        color: white !important;
                        border-color: #c0392b !important;
                    }
                    /* Style pour les badges */
                    .badge-crypto {
                        background-color: #2980b9 !important;
                        color: white !important;
                    }
                    /* Style pour les cartes */
                    .card-crypto {
                        border-color: #3498db !important;
                    }
                    .card-crypto .card-header {
                        background-color: #2c3e50 !important;
                        color: white !important;
                    }
                </style>
            </head>
            <body>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        '''
        
        # Créer le layout
        self._create_layout()
        
        # Initialiser les callbacks
        self._init_callbacks()
        
        logger.info("Dashboard initialisé")
    
    def _preload_data(self):
        """
        Précharge les données des cryptos principales.
        """
        logger.info("Préchargement des données des cryptos principales...")
        
        # Précharger les données des 10 premières cryptos
        for symbol in config.CRYPTO_TICKERS[:10]:
            try:
                logger.info(f"Préchargement des données de {symbol}...")
                self.data_fetcher.get_ticker_data(
                    symbol,
                    "1d",
                    6,
                    force_refresh=True
                )
            except Exception as e:
                logger.error(f"Erreur lors du préchargement des données de {symbol}: {e}")
        
        logger.info("Préchargement des données terminé.")
    
    def _create_layout(self):
        """
        Crée le layout de l'application.
        """
        # Créer les onglets
        tabs = dbc.Tabs([
            dbc.Tab(self._create_dashboard_tab(), label="Tableau de Bord", tab_id="tab-dashboard"),
            dbc.Tab(self._create_backtest_tab(), label="Backtest", tab_id="tab-backtest"),
            dbc.Tab(self._create_watchlist_tab(), label="Liste de Surveillance", tab_id="tab-watchlist"),
            dbc.Tab(self._create_settings_tab(), label="Paramètres", tab_id="tab-settings")
        ], id="tabs", active_tab="tab-dashboard")
        
        # Store pour stocker les valeurs à transmettre entre les onglets
        store = dcc.Store(id='tab-navigation-store')
        
        # Créer le layout principal
        self.app.layout = dbc.Container([
            store,
            dbc.Row([
                dbc.Col([
                    html.H1(config.APP_CONFIG["title"], className="text-center my-4"),
                    html.Hr()
                ])
            ]),
            
            dbc.Row([
                dbc.Col([
                    tabs
                ])
            ]),
            
            # Pied de page
            dbc.Row([
                dbc.Col([
                    html.Hr(),
                    html.P(
                        "TvBin - Analyse technique des cryptomonnaies avec ZLMA Trend Levels",
                        className="text-center text-muted"
                    )
                ])
            ])
        ], fluid=True)
    
    def _create_dashboard_tab(self):
        """Crée l'onglet du tableau de bord."""
        # Créer les options pour les cryptos
        crypto_options = []
        # Ajouter un séparateur
        crypto_options.append({"label": "--- Top Cryptos ---", "value": "", "disabled": True})
        # Charger la liste dynamique
        try:
            with open(config.CRYPTO_TICKERS_PATH, "r") as f:
                top_tickers = set(json.load(f))
        except Exception:
            top_tickers = set()
        # Ajouter les options pour les cryptos
        for symbol in config.CRYPTO_TICKERS:
            if symbol in top_tickers:
                crypto_options.append({"label": f"{symbol}", "value": symbol})
            else:
                crypto_options.append({"label": f"⚠️ {symbol}", "value": symbol, "style": {"color": "orange"}})
        
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Configuration"),
                        dbc.CardBody([
                            dbc.Form([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Sélection de Crypto"),
                                        dcc.Dropdown(
                                            id="symbol-dropdown",
                                            options=crypto_options,
                                            value="BTC",
                                            clearable=False
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Label("Intervalle de temps"),
                                        dcc.Dropdown(
                                            id="timeframe-dropdown",
                                            options=[
                                                {"label": "12 Heures", "value": "12h"},
                                                {"label": "Journalier", "value": "1d"},
                                                {"label": "Hebdomadaire", "value": "1w"}
                                            ],
                                            value="1d",
                                            clearable=False
                                        )
                                    ], width=6)
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Période EMA"),
                                        dbc.Input(
                                            id="ema-period-input",
                                            type="number",
                                            min=5,
                                            max=50,
                                            step=1,
                                            value=config.INDICATOR_CONFIG["ema_period"]
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        dbc.Label("Période ZLMA"),
                                        dbc.Input(
                                            id="zlma-period-input",
                                            type="number",
                                            min=5,
                                            max=50,
                                            step=1,
                                            value=config.INDICATOR_CONFIG["zlma_period"]
                                        )
                                    ], width=6)
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Button(
                                            "Appliquer",
                                            id="apply-button",
                                            color="primary",
                                            className="mt-3"
                                        )
                                    ], width=12)
                                ])
                            ])
                        ])
                    ], className="mb-4 card-crypto")
                ])
            ]),
            
            # Alertes pour les tickers non trouvés
            dbc.Row([
                dbc.Col([
                    html.Div(id="alerts-container")
                ])
            ]),
            
            # Informations sur la dernière mise à jour
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Informations"),
                        dbc.CardBody([
                            html.Div(id="last-update-info")
                        ])
                    ], className="mb-4 card-crypto")
                ])
            ]),
            
            # Graphique principal
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Graphique"),
                        dbc.CardBody([
                            dcc.Loading(
                                id="loading-graph",
                                type="circle",
                                children=[
                                    dcc.Graph(
                                        id="main-graph",
                                        style={"height": "600px"}
                                    )
                                ]
                            )
                        ])
                    ], className="mb-4 card-crypto")
                ])
            ]),
            
            # Signaux détectés
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Signaux Détectés"),
                        dbc.CardBody([
                            html.Div(id="signals-container")
                        ])
                    ], className="mb-4 card-crypto")
                ])
            ]),
            
            # Informations sur le volume
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Volume 24h"),
                        dbc.CardBody([
                            html.Div(id="volume-info")
                        ])
                    ], className="mb-4 card-crypto")
                ], width=6),
                
                # Informations sur la tendance
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Tendance"),
                        dbc.CardBody([
                            html.Div(id="trend-info")
                        ])
                    ], className="mb-4 card-crypto")
                ], width=6)
            ])
        ], fluid=True)
    
    def _create_backtest_tab(self):
        """Crée l'onglet de backtest."""
        return dbc.Container([
            html.H2("Backtest", className="mb-4"),
            html.P("Testez vos stratégies de trading sur des données historiques."),
            
            dbc.Card([
                dbc.CardHeader("Configuration du Backtest"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Sélection de Crypto"),
                            dcc.Dropdown(
                                id="backtest-symbol-dropdown",
                                options=[{"label": ticker, "value": ticker} for ticker in config.CRYPTO_TICKERS],
                                value="BTC",
                                clearable=False
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Intervalle de temps"),
                            dcc.Dropdown(
                                id="backtest-timeframe-dropdown",
                                options=[
                                    {"label": "12 Heures", "value": "12h"},
                                    {"label": "Journalier", "value": "1d"},
                                    {"label": "Hebdomadaire", "value": "1w"}
                                ],
                                value="1d",
                                clearable=False
                            )
                        ], width=6)
                    ]),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Date de début"),
                            dcc.DatePickerSingle(
                                id="backtest-start-date",
                                date=(datetime.now() - timedelta(days=180)).date(),
                                display_format="YYYY-MM-DD"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Date de fin"),
                            dcc.DatePickerSingle(
                                id="backtest-end-date",
                                date=datetime.now().date(),
                                display_format="YYYY-MM-DD"
                            )
                        ], width=6)
                    ], className="mt-3"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Lancer le Backtest",
                                id="run-backtest-button",
                                color="primary",
                                className="mt-3"
                            )
                        ])
                    ])
                ])
            ], className="mb-4"),
            
            # Résultats du backtest
            dbc.Card([
                dbc.CardHeader("Résultats du Backtest"),
                dbc.CardBody([
                    dcc.Loading(
                        id="loading-backtest",
                        type="circle",
                        children=[
                            html.Div(id="backtest-results")
                        ]
                    )
                ])
            ])
        ], fluid=True)
    
    def _create_settings_tab(self):
        """Crée l'onglet des paramètres."""
        # Ajout du bouton d'arrêt
        stop_button = dbc.Button(
            "Arrêter le logiciel",
            id="stop-app-button",
            color="danger",
            className="mb-2"
        )
        return dbc.Container([
            html.H2("Paramètres", className="mb-4"),
            html.P("Configurez les paramètres de l'application."),
            # Affichage des ajouts/suppressions de tickers
            html.Div(id="tickers-update-info"),
            dbc.Card([
                dbc.CardHeader("Service de Surveillance"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Démarrer/Arrêter le Service",
                                id="monitoring-button",
                                color="primary"
                            ),
                            html.Div(id="monitoring-status", className="mt-3")
                        ])
                    ])
                ])
            ], className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Notifications Discord"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Webhook URL"),
                            dbc.Input(
                                id="discord-webhook-input",
                                type="text",
                                value=config.DISCORD_WEBHOOK,
                                placeholder="Entrez l'URL du webhook Discord"
                            )
                        ])
                    ]),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Tester la Notification",
                                id="test-discord-button",
                                color="primary",
                                className="mt-3"
                            ),
                            html.Div(id="discord-test-result", className="mt-2")
                        ])
                    ])
                ])
            ], className="mb-4"),
            
            dbc.Card([
                dbc.CardHeader("Paramètres API Binance"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("API Key"),
                            dbc.Input(
                                id="binance-api-key-input",
                                type="password",
                                value=config.BINANCE_API_KEY,
                                placeholder="Entrez votre clé API Binance"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Label("API Secret"),
                            dbc.Input(
                                id="binance-api-secret-input",
                                type="password",
                                value=config.BINANCE_API_SECRET,
                                placeholder="Entrez votre secret API Binance"
                            )
                        ], width=6)
                    ]),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Sauvegarder",
                                id="save-binance-button",
                                color="primary",
                                className="mt-3"
                            ),
                            html.Div(id="binance-save-result", className="mt-2")
                        ])
                    ])
                ])
            ]),
            dbc.Card([
                dbc.CardHeader("Mise à jour des tickers CoinMarketCap"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Mettre à jour les tickers CoinMarketCap",
                                id="update-cmc-tickers-button",
                                color="warning",
                                className="mb-2"
                            ),
                            html.Div(id="update-cmc-tickers-result", className="mt-2")
                        ])
                    ])
                ])
            ], className="mb-4"),
            stop_button,
        ], fluid=True)
    
    def _init_callbacks(self):
        """
        Initialise les callbacks de l'application.
        """
        # Callback pour mettre à jour le graphique
        @self.app.callback(
            [
                Output("main-graph", "figure"),
                Output("signals-container", "children"),
                Output("last-update-info", "children"),
                Output("volume-info", "children"),
                Output("trend-info", "children"),
                Output("alerts-container", "children")
            ],
            [Input("apply-button", "n_clicks")],
            [
                State("symbol-dropdown", "value"),
                State("timeframe-dropdown", "value"),
                State("ema-period-input", "value"),
                State("zlma-period-input", "value")
            ]
        )
        def update_graph(n_clicks, symbol, timeframe, ema_period, zlma_period):
            """
            Met à jour le graphique et les informations associées.
            """
            if n_clicks is None:
                # Première exécution, utiliser les valeurs par défaut
                symbol = "BTC"
                timeframe = "1d"
                ema_period = config.INDICATOR_CONFIG["ema_period"]
                zlma_period = config.INDICATOR_CONFIG["zlma_period"]
            
            # Mettre à jour les périodes des indicateurs
            self.indicator_calculator.ema_period = ema_period
            self.indicator_calculator.zlma_period = zlma_period
            
            # Récupérer les données
            data = self.data_fetcher.get_ticker_data(symbol, timeframe)
            
            # Vérifier si les données sont vides
            if data.empty:
                # Créer une alerte
                alert = dbc.Alert(
                    f"⚠️ Impossible de récupérer les données pour {symbol}. Vérifiez que ce symbole existe sur Binance.",
                    color="danger",
                    dismissable=True,
                    className="mt-3 alert-crypto"
                )
                
                # Créer un graphique vide
                fig = go.Figure()
                fig.update_layout(
                    title=f"Aucune donnée disponible pour {symbol}",
                    xaxis_title="Date",
                    yaxis_title="Prix",
                    template="plotly_dark"
                )
                
                return fig, "Aucun signal détecté", "Aucune donnée disponible", "Volume: N/A", "Tendance: N/A", alert
            
            # Calculer les indicateurs
            data_with_indicators = self.indicator_calculator.add_indicators(data)
            
            # Créer le graphique
            fig = make_subplots(
                rows=2, 
                cols=1, 
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3],
                subplot_titles=(f"{symbol} - {timeframe}", "Volume")
            )
            
            # Ajouter les chandeliers
            fig.add_trace(
                go.Candlestick(
                    x=data_with_indicators.index,
                    open=data_with_indicators['Open'],
                    high=data_with_indicators['High'],
                    low=data_with_indicators['Low'],
                    close=data_with_indicators['Close'],
                    name="Prix"
                ),
                row=1, col=1
            )
            
            # Ajouter l'EMA
            fig.add_trace(
                go.Scatter(
                    x=data_with_indicators.index,
                    y=data_with_indicators['EMA'],
                    name=f"EMA({ema_period})",
                    line=dict(color='orange', width=2)
                ),
                row=1, col=1
            )
            
            # Ajouter le ZLMA
            fig.add_trace(
                go.Scatter(
                    x=data_with_indicators.index,
                    y=data_with_indicators['ZLMA'],
                    name=f"ZLMA({zlma_period})",
                    line=dict(color='blue', width=2)
                ),
                row=1, col=1
            )
            
            # Ajouter les signaux
            signals = data_with_indicators[data_with_indicators['Signal'] != 0]
            
            if not signals.empty:
                # Signaux d'achat (1)
                buy_signals = signals[signals['Signal'] == 1]
                if not buy_signals.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=buy_signals.index,
                            y=buy_signals['Low'] * 0.99,  # Légèrement en dessous pour la visibilité
                            name="Achat",
                            mode="markers",
                            marker=dict(
                                symbol="triangle-up",
                                size=15,
                                color="green",
                                line=dict(width=2, color="darkgreen")
                            )
                        ),
                        row=1, col=1
                    )
                
                # Signaux de vente (-1)
                sell_signals = signals[signals['Signal'] == -1]
                if not sell_signals.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=sell_signals.index,
                            y=sell_signals['High'] * 1.01,  # Légèrement au-dessus pour la visibilité
                            name="Vente",
                            mode="markers",
                            marker=dict(
                                symbol="triangle-down",
                                size=15,
                                color="red",
                                line=dict(width=2, color="darkred")
                            )
                        ),
                        row=1, col=1
                    )
            
            # Ajouter le volume
            fig.add_trace(
                go.Bar(
                    x=data_with_indicators.index,
                    y=data_with_indicators['Volume'],
                    name="Volume",
                    marker=dict(
                        color='rgba(52, 152, 219, 0.7)'
                    )
                ),
                row=2, col=1
            )
            
            # Mettre à jour le layout
            fig.update_layout(
                title=f"{symbol} - {timeframe}",
                xaxis_title="Date",
                yaxis_title="Prix",
                template="plotly_dark",
                height=600,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Mettre à jour les axes
            fig.update_xaxes(
                rangeslider_visible=False,
                gridcolor='rgba(255, 255, 255, 0.1)'
            )
            
            fig.update_yaxes(
                gridcolor='rgba(255, 255, 255, 0.1)'
            )
            
            # Créer le contenu des signaux
            signals_content = []
            
            if not signals.empty:
                signals_df = signals.sort_index(ascending=False).head(10)  # 10 derniers signaux
                
                signals_table = dbc.Table(
                    [
                        html.Thead(
                            html.Tr([
                                html.Th("Date"),
                                html.Th("Type"),
                                html.Th("Prix")
                            ])
                        ),
                        html.Tbody([
                            html.Tr([
                                html.Td(row.name.strftime('%Y-%m-%d')),
                                html.Td(
                                    "Achat" if row['Signal'] == 1 else "Vente",
                                    style={
                                        "color": "green" if row['Signal'] == 1 else "red",
                                        "font-weight": "bold"
                                    }
                                ),
                                html.Td(f"{row['Close']:.2f}")
                            ]) for _, row in signals_df.iterrows()
                        ])
                    ],
                    bordered=True,
                    hover=True,
                    responsive=True,
                    striped=True
                )
                
                signals_content.append(signals_table)
            else:
                signals_content.append(html.P("Aucun signal détecté"))
            
            # Créer le contenu de la dernière mise à jour
            last_update = data.index[-1].strftime('%Y-%m-%d')
            last_price = data['Close'].iloc[-1]
            
            last_update_content = [
                html.P([
                    html.Strong("Dernière mise à jour: "),
                    last_update
                ]),
                html.P([
                    html.Strong("Dernier prix: "),
                    f"{last_price:.2f}"
                ]),
                html.P([
                    html.Strong("Nombre de points de données: "),
                    f"{len(data)}"
                ])
            ]
            
            # Créer le contenu du volume
            last_volume = data['Volume'].iloc[-1]
            avg_volume = data['Volume'].mean()
            
            volume_content = [
                html.P([
                    html.Strong("Volume actuel: "),
                    f"{last_volume:.2f}"
                ]),
                html.P([
                    html.Strong("Volume moyen: "),
                    f"{avg_volume:.2f}"
                ]),
                html.P([
                    html.Strong("Ratio volume/moyenne: "),
                    f"{(last_volume / avg_volume):.2f}"
                ])
            ]
            
            # Créer le contenu de la tendance
            if 'Trend' in data_with_indicators.columns:
                last_trend = data_with_indicators['Trend'].iloc[-1]
                trend_text = "Haussière" if last_trend == 1 else "Baissière" if last_trend == -1 else "Neutre"
                trend_color = "green" if last_trend == 1 else "red" if last_trend == -1 else "gray"
                
                trend_content = [
                    html.P([
                        html.Strong("Tendance actuelle: "),
                        html.Span(
                            trend_text,
                            style={"color": trend_color, "font-weight": "bold"}
                        )
                    ]),
                    html.P([
                        html.Strong("EMA: "),
                        f"{data_with_indicators['EMA'].iloc[-1]:.2f}"
                    ]),
                    html.P([
                        html.Strong("ZLMA: "),
                        f"{data_with_indicators['ZLMA'].iloc[-1]:.2f}"
                    ])
                ]
            else:
                trend_content = [html.P("Tendance: N/A")]
            
            # Pas d'alerte si les données sont disponibles
            alert = None
            
            return fig, signals_content, last_update_content, volume_content, trend_content, alert
        
        # Callback pour le backtest
        @self.app.callback(
            Output("backtest-results", "children"),
            [Input("run-backtest-button", "n_clicks")],
            [
                State("backtest-symbol-dropdown", "value"),
                State("backtest-timeframe-dropdown", "value"),
                State("backtest-start-date", "date"),
                State("backtest-end-date", "date")
            ]
        )
        def run_backtest(n_clicks, symbol, timeframe, start_date, end_date):
            """
            Exécute le backtest avec les paramètres sélectionnés.
            """
            if n_clicks is None:
                raise PreventUpdate
            
            # Exécuter le backtest
            results = self.backtester.run_backtest(
                ticker=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            if not results["success"]:
                return dbc.Alert(
                    f"Erreur lors du backtest: {results['error']}",
                    color="danger",
                    dismissable=True
                )
            
            # Créer le résumé des résultats
            stats = results["results"]
            
            summary = dbc.Card([
                dbc.CardHeader("Résumé du Backtest"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H5("Performance"),
                            html.Hr(),
                            html.P([
                                html.Strong("Capital initial: "),
                                f"{stats['initial_capital']:,.2f} USDT"
                            ]),
                            html.P([
                                html.Strong("Capital final: "),
                                f"{stats['final_capital']:,.2f} USDT"
                            ]),
                            html.P([
                                html.Strong("Rendement total: "),
                                html.Span(
                                    f"{stats['total_return']:,.2f}%",
                                    style={
                                        "color": "green" if stats['total_return'] > 0 else "red",
                                        "font-weight": "bold"
                                    }
                                )
                            ]),
                            html.P([
                                html.Strong("Drawdown maximum: "),
                                f"{stats['max_drawdown']:,.2f}%"
                            ])
                        ], width=6),
                        dbc.Col([
                            html.H5("Statistiques des Trades"),
                            html.Hr(),
                            html.P([
                                html.Strong("Nombre total de trades: "),
                                f"{stats['total_trades']}"
                            ]),
                            html.P([
                                html.Strong("Trades gagnants: "),
                                f"{stats['winning_trades']}"
                            ]),
                            html.P([
                                html.Strong("Trades perdants: "),
                                f"{stats['losing_trades']}"
                            ]),
                            html.P([
                                html.Strong("Taux de réussite: "),
                                f"{stats['win_rate']:,.2f}%"
                            ]),
                            html.P([
                                html.Strong("Gain moyen: "),
                                f"{stats['avg_win']:,.2f} USDT"
                            ]),
                            html.P([
                                html.Strong("Perte moyenne: "),
                                f"{stats['avg_loss']:,.2f} USDT"
                            ])
                        ], width=6)
                    ])
                ])
            ])
            
            # Créer le tableau des trades
            trades = stats["trades"]
            if trades:
                trades_table = dbc.Table(
                    [
                        html.Thead(
                            html.Tr([
                                html.Th("Date d'entrée"),
                                html.Th("Prix d'entrée"),
                                html.Th("Direction"),
                                html.Th("Date de sortie"),
                                html.Th("Prix de sortie"),
                                html.Th("P&L"),
                                html.Th("P&L %")
                            ])
                        ),
                        html.Tbody([
                            html.Tr([
                                html.Td(trade["date_entry"]),
                                html.Td(f"{trade['price_entry']:.2f}"),
                                html.Td(
                                    trade["direction"],
                                    style={
                                        "color": "green" if trade["direction"] == "LONG" else "red",
                                        "font-weight": "bold"
                                    }
                                ),
                                html.Td(trade.get("date_exit", "En cours")),
                                html.Td(f"{trade.get('price_exit', 0):.2f}"),
                                html.Td(
                                    f"{trade.get('pnl', 0):,.2f}",
                                    style={
                                        "color": "green" if trade.get('pnl', 0) > 0 else "red",
                                        "font-weight": "bold"
                                    }
                                ),
                                html.Td(
                                    f"{trade.get('pnl_pct', 0):,.2f}%",
                                    style={
                                        "color": "green" if trade.get('pnl_pct', 0) > 0 else "red",
                                        "font-weight": "bold"
                                    }
                                )
                            ]) for trade in trades
                        ])
                    ],
                    bordered=True,
                    hover=True,
                    responsive=True,
                    striped=True,
                    className="mt-4"
                )
            else:
                trades_table = html.P("Aucun trade effectué pendant la période.")
            
            return html.Div([
                summary,
                html.H5("Détail des Trades", className="mt-4"),
                trades_table
            ])
        
        # Callback pour démarrer/arrêter le service de surveillance
        @self.app.callback(
            Output("monitoring-status", "children"),
            [Input("monitoring-button", "n_clicks")]
        )
        def toggle_monitoring(n_clicks):
            """
            Démarre ou arrête le service de surveillance.
            """
            if n_clicks is None:
                return "Service de surveillance: Arrêté"
            
            if n_clicks % 2 == 1:
                # Démarrer le service
                self.monitoring_service.start()
                return "Service de surveillance: En cours"
            else:
                # Arrêter le service
                self.monitoring_service.stop()
                return "Service de surveillance: Arrêté"
        
        # Initialiser les callbacks pour la liste de surveillance
        self._setup_callbacks()

    def _create_watchlist_tab(self):
        """Crée l'onglet de liste de surveillance."""
        # Sélecteur de ticker
        ticker_selector = dbc.Card([
            dbc.CardHeader("Ajouter un Ticker"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Sélectionner un ou plusieurs tickers"),
                        html.Div([
                            dcc.Dropdown(
                                id="watchlist-ticker-dropdown",
                                options=[{"label": ticker, "value": ticker} for ticker in config.CRYPTO_TICKERS],
                                value=[],
                                multi=True,
                                placeholder="Sélectionnez des tickers..."
                            ),
                            dbc.Button(
                                "Sélectionner Tous",
                                id="select-all-tickers-button",
                                color="secondary",
                                size="sm",
                                className="mt-2"
                            )
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Timeframe"),
                        dbc.RadioItems(
                            id="watchlist-timeframe-radio",
                            options=[
                                {"label": "Journalier", "value": "1d"},
                                {"label": "Hebdomadaire", "value": "1w"}
                            ],
                            value="1d",
                            inline=True
                        )
                    ], width=6)
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            "Ajouter à la Liste de Surveillance",
                            id="add-to-watchlist-button",
                            color="primary",
                            className="mt-3"
                        ),
                        html.Div(id="watchlist-add-message", className="mt-2")
                    ])
                ])
            ])
        ], className="mb-4")
        
        # Tableau de la liste de surveillance
        watchlist_table = dbc.Card([
            dbc.CardHeader("Liste de Surveillance"),
            dbc.CardBody([
                html.Div(id="watchlist-table-container", children=[
                    html.P("Aucun ticker dans la liste de surveillance.", id="empty-watchlist-message"),
                    dbc.Table(
                        [
                            html.Thead(
                                html.Tr([
                                    html.Th("Ticker"),
                                    html.Th("Timeframe"),
                                    html.Th("Dernier Signal"),
                                    html.Th("Date du Signal"),
                                    html.Th("Notifications"),
                                    html.Th("Actions")
                                ])
                            ),
                            html.Tbody(id="watchlist-table-body")
                        ],
                        id="watchlist-table",
                        bordered=True,
                        hover=True,
                        responsive=True,
                        striped=True,
                        className="d-none"
                    )
                ])
            ])
        ])
        
        # Mettre à jour le contenu de la liste de surveillance
        interval = dcc.Interval(
            id="watchlist-update-interval",
            interval=60 * 1000,  # Mettre à jour toutes les minutes
            n_intervals=0
        )
        
        return dbc.Container([
            html.H2("Liste de Surveillance", className="mb-4"),
            html.P("Ajoutez des tickers à surveiller et recevez des notifications Discord en cas de croisement."),
            ticker_selector,
            watchlist_table,
            interval
        ], fluid=True)

    def _setup_callbacks(self):
        """Configure les callbacks de l'application."""
        # Callbacks pour la liste de surveillance
        @self.app.callback(
            [Output("watchlist-add-message", "children"),
             Output("watchlist-table-body", "children"),
             Output("watchlist-table", "className"),
             Output("empty-watchlist-message", "className")],
            [Input("add-to-watchlist-button", "n_clicks"),
             Input("watchlist-update-interval", "n_intervals")],
            [State("watchlist-ticker-dropdown", "value"),
             State("watchlist-timeframe-radio", "value")]
        )
        def update_watchlist(n_clicks, n_intervals, selected_tickers, timeframe):
            """Met à jour la liste de surveillance."""
            ctx = dash.callback_context
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
            
            # Récupérer la liste de surveillance actuelle
            watchlist = self.monitoring_service.get_watchlist_manager().get_watchlist()
            # Créer une copie du dictionnaire pour l'itération
            watchlist_copy = dict(watchlist)
            
            # Ajouter des tickers à la liste de surveillance
            if triggered_id == "add-to-watchlist-button" and n_clicks and selected_tickers:
                success_count = 0
                error_count = 0
                
                for ticker in selected_tickers:
                    if self.monitoring_service.get_watchlist_manager().add_to_watchlist(ticker, timeframe):
                        # Récupérer les données et calculer le dernier signal
                        try:
                            # Détecter les signaux avec le SignalDetector
                            signals = self.signal_detector.detect_signals(ticker, timeframe)
                            if signals and "all_signals" in signals:
                                # Utiliser le dernier signal de la liste all_signals
                                last_signal_data = signals["all_signals"][-1] if signals["all_signals"] else None
                                if last_signal_data:
                                    last_signal = last_signal_data["signal"]
                                    last_signal_date = last_signal_data["date"]
                                    
                                    # Mettre à jour le signal dans la watchlist
                                    self.monitoring_service.get_watchlist_manager().update_signal(
                                        ticker,
                                        last_signal,
                                        last_signal_date
                                    )
                        except Exception as e:
                            logger.error(f"Erreur lors de la récupération des signaux pour {ticker}: {e}")
                        
                        success_count += 1
                    else:
                        error_count += 1
                
                # Mettre à jour la liste de surveillance
                watchlist = self.monitoring_service.get_watchlist_manager().get_watchlist()
                watchlist_copy = dict(watchlist)
                
                # Créer le message de confirmation
                if success_count > 0 and error_count == 0:
                    message = dbc.Alert(f"{success_count} ticker(s) ajouté(s) à la liste de surveillance.", color="success")
                elif success_count > 0 and error_count > 0:
                    message = dbc.Alert(f"{success_count} ticker(s) ajouté(s), {error_count} erreur(s).", color="warning")
                else:
                    message = dbc.Alert(f"Erreur: Impossible d'ajouter les tickers à la liste de surveillance.", color="danger")
            else:
                message = None
                
                # Mettre à jour les signaux pour tous les tickers si c'est une mise à jour périodique
                if triggered_id == "watchlist-update-interval":
                    # Créer une copie du dictionnaire pour éviter l'erreur de modification pendant l'itération
                    watchlist_copy = dict(watchlist)
                    for ticker, info in watchlist_copy.items():
                        try:
                            # Détecter les signaux avec le SignalDetector
                            signals = self.signal_detector.detect_signals(ticker, info["timeframe"])
                            if signals and signals["last_signal"]:
                                last_signal = signals["last_signal"]["signal"]
                                last_signal_date = signals["last_signal"]["date"]
                                
                                # Mettre à jour le signal dans la watchlist
                                self.monitoring_service.get_watchlist_manager().update_signal(
                                    ticker,
                                    last_signal,
                                    last_signal_date
                                )
                        except Exception as e:
                            logger.error(f"Erreur lors de la mise à jour des signaux pour {ticker}: {e}")
                    
                    # Récupérer la liste mise à jour
                    watchlist = self.monitoring_service.get_watchlist_manager().get_watchlist()
                    watchlist_copy = dict(watchlist)
            
            # Créer les lignes du tableau
            rows = []
            
            # Convertir le dictionnaire en liste pour le tri
            watchlist_items = []
            for ticker, info in watchlist_copy.items():
                # Convertir la date en objet datetime pour le tri
                try:
                    if info["last_signal_date"] and isinstance(info["last_signal_date"], str):
                        signal_date = datetime.strptime(info["last_signal_date"], "%Y-%m-%d")
                    elif info["last_signal_date"]:
                        signal_date = info["last_signal_date"]
                    else:
                        signal_date = datetime.min
                except Exception:
                    signal_date = datetime.min
                
                watchlist_items.append((ticker, info, signal_date))
            
            # Trier par date de signal (du plus récent au plus ancien)
            watchlist_items.sort(key=lambda x: x[2], reverse=True)
            
            # Créer les lignes du tableau avec les données triées
            for ticker, info, _ in watchlist_items:
                # Déterminer le type de signal et la tendance
                signal = info["last_signal"]
                if signal == 1:
                    signal_text = "HAUSSIER 📈"
                    signal_color = "success"
                    trend_text = "Tendance haussière"
                elif signal == -1:
                    signal_text = "BAISSIER 📉"
                    signal_color = "danger"
                    trend_text = "Tendance baissière"
                else:
                    signal_text = "AUCUN"
                    signal_color = "secondary"
                    trend_text = "Pas de tendance"
                
                # Déterminer le timeframe
                timeframe_text = "Journalier" if info["timeframe"] == "1d" else "Hebdomadaire"
                
                # Déterminer l'état des notifications
                notifications_enabled = info["notifications_enabled"]
                notifications_text = "Activées" if notifications_enabled else "Désactivées"
                notifications_color = "success" if notifications_enabled else "danger"
                
                # Formater la date du signal
                signal_date = info["last_signal_date"] if info["last_signal_date"] else "N/A"
                
                # Créer la ligne du tableau avec la tendance
                row = html.Tr([
                    html.Td(ticker),
                    html.Td(timeframe_text),
                    html.Td([
                        dbc.Badge(signal_text, color=signal_color, className="p-2"),
                        html.Div(trend_text, className="small text-muted mt-1")
                    ]),
                    html.Td(signal_date),
                    html.Td(dbc.Badge(notifications_text, color=notifications_color, className="p-2")),
                    html.Td([
                        dbc.ButtonGroup([
                            dbc.Button(
                                "Voir Graphique",
                                id={"type": "view-chart-button", "index": f"{ticker}_{info['timeframe']}"},
                                color="info",
                                size="sm",
                                className="me-1"
                            ),
                            dbc.Button(
                                "Notifications",
                                id={"type": "toggle-notifications-button", "index": ticker},
                                color="primary",
                                size="sm",
                                className="me-1"
                            ),
                            dbc.Button(
                                "Supprimer",
                                id={"type": "remove-from-watchlist-button", "index": ticker},
                                color="danger",
                                size="sm"
                            )
                        ])
                    ])
                ])
                
                rows.append(row)
            
            # Déterminer si le tableau doit être affiché
            if rows:
                table_class = "table"
                empty_message_class = "d-none"
            else:
                table_class = "d-none"
                empty_message_class = ""
            
            return message, rows, table_class, empty_message_class
        
        @self.app.callback(
            Output("watchlist-table-body", "children", allow_duplicate=True),
            Input({"type": "toggle-notifications-button", "index": ALL}, "n_clicks"),
            prevent_initial_call=True
        )
        def toggle_notifications(n_clicks):
            """Active ou désactive les notifications pour un ticker."""
            if not any(n_clicks):
                raise PreventUpdate
            
            ctx = dash.callback_context
            if not ctx.triggered:
                raise PreventUpdate
                
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            ticker = json.loads(button_id)["index"]
            
            # Activer ou désactiver les notifications
            self.monitoring_service.get_watchlist_manager().toggle_notifications(ticker)
            
            # Mettre à jour la liste de surveillance
            watchlist = self.monitoring_service.get_watchlist_manager().get_watchlist()
            
            # Créer les lignes du tableau
            rows = []
            
            # Convertir le dictionnaire en liste pour le tri
            watchlist_items = []
            for ticker, info in watchlist.items():
                try:
                    if info["last_signal_date"] and isinstance(info["last_signal_date"], str):
                        signal_date = datetime.strptime(info["last_signal_date"], "%Y-%m-%d")
                    elif info["last_signal_date"]:
                        signal_date = info["last_signal_date"]
                    else:
                        signal_date = datetime.min
                except Exception:
                    signal_date = datetime.min
                
                watchlist_items.append((ticker, info, signal_date))
            
            # Trier par date de signal (du plus récent au plus ancien)
            watchlist_items.sort(key=lambda x: x[2], reverse=True)
            
            # Créer les lignes du tableau avec les données triées
            for ticker, info, _ in watchlist_items:
                # Déterminer le type de signal et la tendance
                signal = info["last_signal"]
                if signal == 1:
                    signal_text = "HAUSSIER 📈"
                    signal_color = "success"
                    trend_text = "Tendance haussière"
                elif signal == -1:
                    signal_text = "BAISSIER 📉"
                    signal_color = "danger"
                    trend_text = "Tendance baissière"
                else:
                    signal_text = "AUCUN"
                    signal_color = "secondary"
                    trend_text = "Pas de tendance"
                
                # Déterminer le timeframe
                timeframe_text = "Journalier" if info["timeframe"] == "1d" else "Hebdomadaire"
                
                # Déterminer l'état des notifications
                notifications_enabled = info["notifications_enabled"]
                notifications_text = "Activées" if notifications_enabled else "Désactivées"
                notifications_color = "success" if notifications_enabled else "danger"
                
                # Formater la date du signal
                signal_date = info["last_signal_date"] if info["last_signal_date"] else "N/A"
                
                # Créer la ligne du tableau avec la tendance
                row = html.Tr([
                    html.Td(ticker),
                    html.Td(timeframe_text),
                    html.Td([
                        dbc.Badge(signal_text, color=signal_color, className="p-2"),
                        html.Div(trend_text, className="small text-muted mt-1")
                    ]),
                    html.Td(signal_date),
                    html.Td(dbc.Badge(notifications_text, color=notifications_color, className="p-2")),
                    html.Td([
                        dbc.ButtonGroup([
                            dbc.Button(
                                "Voir Graphique",
                                id={"type": "view-chart-button", "index": f"{ticker}_{info['timeframe']}"},
                                color="info",
                                size="sm",
                                className="me-1"
                            ),
                            dbc.Button(
                                "Notifications",
                                id={"type": "toggle-notifications-button", "index": ticker},
                                color="primary",
                                size="sm",
                                className="me-1"
                            ),
                            dbc.Button(
                                "Supprimer",
                                id={"type": "remove-from-watchlist-button", "index": ticker},
                                color="danger",
                                size="sm"
                            )
                        ])
                    ])
                ])
                
                rows.append(row)
            
            return rows
        
        @self.app.callback(
            [
                Output("watchlist-table-body", "children", allow_duplicate=True),
                Output("watchlist-table", "className", allow_duplicate=True),
                Output("empty-watchlist-message", "className", allow_duplicate=True)
            ],
            Input({"type": "remove-from-watchlist-button", "index": ALL}, "n_clicks"),
            prevent_initial_call=True
        )
        def remove_from_watchlist(n_clicks):
            """Supprime un ticker de la liste de surveillance."""
            if not any(n_clicks):
                raise PreventUpdate
            
            ctx = dash.callback_context
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            ticker = json.loads(button_id)["index"]
            
            # Supprimer le ticker de la liste de surveillance
            self.monitoring_service.get_watchlist_manager().remove_from_watchlist(ticker)
            
            # Mettre à jour la liste de surveillance
            watchlist = self.monitoring_service.get_watchlist_manager().get_watchlist()
            
            # Créer les lignes du tableau
            rows = []
            
            for ticker, info in watchlist.items():
                # Déterminer le type de signal
                signal = info["last_signal"]
                if signal == 1:
                    signal_text = "HAUSSIER 📈"
                    signal_color = "success"
                elif signal == -1:
                    signal_text = "BAISSIER 📉"
                    signal_color = "danger"
                else:
                    signal_text = "AUCUN"
                    signal_color = "secondary"
                
                # Déterminer le timeframe
                timeframe_text = "Journalier" if info["timeframe"] == "1d" else "Hebdomadaire"
                
                # Déterminer l'état des notifications
                notifications_enabled = info["notifications_enabled"]
                notifications_text = "Activées" if notifications_enabled else "Désactivées"
                notifications_color = "success" if notifications_enabled else "danger"
                
                # Créer la ligne du tableau
                row = html.Tr([
                    html.Td(ticker),
                    html.Td(timeframe_text),
                    html.Td(dbc.Badge(signal_text, color=signal_color, className="p-2")),
                    html.Td(info["last_signal_date"] or "N/A"),
                    html.Td(dbc.Badge(notifications_text, color=notifications_color, className="p-2")),
                    html.Td([
                        dbc.ButtonGroup([
                            dbc.Button(
                                "Notifications",
                                id={"type": "toggle-notifications-button", "index": ticker},
                                color="primary",
                                size="sm",
                                className="me-1"
                            ),
                            dbc.Button(
                                "Supprimer",
                                id={"type": "remove-from-watchlist-button", "index": ticker},
                                color="danger",
                                size="sm"
                            )
                        ])
                    ])
                ])
                
                rows.append(row)
            
            # Déterminer si le tableau doit être affiché
            if rows:
                table_class = "table"
                empty_message_class = "d-none"
            else:
                table_class = "d-none"
                empty_message_class = ""
            
            return rows, table_class, empty_message_class

        @self.app.callback(
            Output("discord-test-result", "children"),
            Output("discord-webhook-input", "value"),
            [Input("test-discord-button", "n_clicks")],
            [State("discord-webhook-input", "value")]
        )
        def test_discord_notification(n_clicks, webhook_url):
            """Teste l'envoi d'une notification Discord."""
            if n_clicks is None:
                raise PreventUpdate
            
            # Mettre à jour l'URL du webhook
            self.discord_notifier.webhook_url = webhook_url
            
            # Envoyer un message de test
            success = self.discord_notifier.send_message(
                "🔔 **Test de Notification TvBin**\n\nSi vous voyez ce message, les notifications Discord sont correctement configurées!"
            )
            
            if success:
                return dbc.Alert(
                    "Test réussi! Vérifiez votre canal Discord.",
                    color="success",
                    dismissable=True,
                    duration=4000
                ), webhook_url
            else:
                return dbc.Alert(
                    "Erreur lors de l'envoi du message. Vérifiez l'URL du webhook.",
                    color="danger",
                    dismissable=True
                ), webhook_url

        @self.app.callback(
            Output("watchlist-ticker-dropdown", "value"),
            Input("select-all-tickers-button", "n_clicks"),
            State("watchlist-ticker-dropdown", "options"),
            prevent_initial_call=True
        )
        def select_all_tickers(n_clicks, available_options):
            """Sélectionne tous les tickers disponibles."""
            if n_clicks is None:
                raise PreventUpdate
            
            return [option["value"] for option in available_options]

        @self.app.callback(
            [
                Output("tabs", "active_tab"),
                Output("symbol-dropdown", "value"),
                Output("timeframe-dropdown", "value"),
                Output("apply-button", "n_clicks", allow_duplicate=True)
            ],
            [Input("tab-navigation-store", "data")],
            prevent_initial_call=True
        )
        def navigate_to_dashboard(data):
            """Navigue vers le tableau de bord avec les paramètres spécifiés."""
            if not data:
                raise PreventUpdate
            
            return "tab-dashboard", data["ticker"], data["timeframe"], 1

        @self.app.callback(
            [
                Output("tab-navigation-store", "data"),
                Output("apply-button", "n_clicks")
            ],
            [Input({"type": "view-chart-button", "index": ALL}, "n_clicks")],
            prevent_initial_call=True
        )
        def handle_view_chart(n_clicks):
            """Gère le clic sur le bouton Voir Graphique."""
            if not any(n_clicks):
                raise PreventUpdate
            
            ctx = dash.callback_context
            button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            ticker, timeframe = json.loads(button_id)["index"].split("_")
            
            # Retourner les données pour la navigation et simuler un clic sur le bouton Appliquer
            return {"ticker": ticker, "timeframe": timeframe}, 1

        # Callback pour afficher les ajouts/suppressions de tickers
        @self.app.callback(
            Output("tickers-update-info", "children"),
            Input("tabs", "active_tab")
        )
        def show_tickers_update_info(tab):
            if tab != "tab-settings":
                raise PreventUpdate
            added = getattr(self, "tickers_added", [])
            removed = getattr(self, "tickers_removed", [])
            content = []
            if added:
                content.append(dbc.Alert(f"Tickers ajoutés: {', '.join(added)}", color="success"))
            if removed:
                content.append(dbc.Alert(f"Tickers supprimés: {', '.join(removed)}", color="warning"))
            if not content:
                content.append(html.P("Aucun changement de tickers au démarrage."))
            return content

        # Callback pour forcer la mise à jour manuelle
        @self.app.callback(
            Output("update-cmc-tickers-result", "children"),
            Input("update-cmc-tickers-button", "n_clicks")
        )
        def force_update_cmc_tickers(n_clicks):
            if not n_clicks:
                raise PreventUpdate
            added, removed = self._update_cmc_tickers()
            msg = []
            if added:
                msg.append(dbc.Alert(f"Tickers ajoutés: {', '.join(added)}", color="success"))
            if removed:
                msg.append(dbc.Alert(f"Tickers supprimés: {', '.join(removed)}", color="warning"))
            msg.append(dbc.Alert("Redémarrez le logiciel pour prendre en compte la nouvelle liste de tickers.", color="info"))
            return msg

        # Callback pour arrêter le logiciel
        @self.app.callback(
            Output("stop-app-button", "n_clicks"),
            Input("stop-app-button", "n_clicks")
        )
        def stop_app(n_clicks):
            if n_clicks:
                import os
                os._exit(0)
            raise PreventUpdate

    def _update_cmc_tickers(self):
        """Met à jour la liste des tickers CoinMarketCap et retourne les ajouts/suppressions."""
        import requests
        api_key = config.COINMARKETCAP_API_KEY
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"}
        params = {"limit": 200, "convert": "USD"}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            new_tickers = [coin["symbol"] for coin in data["data"]]
            # Charger l'ancienne liste
            try:
                with open(config.CRYPTO_TICKERS_PATH, "r") as f:
                    old_tickers = json.load(f)
            except Exception:
                old_tickers = []
            # Sauvegarder la nouvelle liste
            with open(config.CRYPTO_TICKERS_PATH, "w") as f:
                json.dump(new_tickers, f, indent=2)
            # Calculer ajouts/suppressions
            added = [t for t in new_tickers if t not in old_tickers]
            removed = [t for t in old_tickers if t not in new_tickers]
            return added, removed
        else:
            return None, None