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

import dash
from dash import dcc, html, callback, Input, Output, State, ALL, MATCH
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
        
        # Précharger les données des cryptos principales
        self._preload_data()
        
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
        # Créer les options pour les cryptos
        crypto_options = []
        
        # Ajouter un séparateur
        crypto_options.append({"label": "--- Top Cryptos ---", "value": "", "disabled": True})
        
        # Ajouter les options pour les cryptos
        for symbol in config.CRYPTO_TICKERS:
            crypto_options.append({"label": f"{symbol}", "value": symbol})
        
        self.app.layout = dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H1(config.APP_CONFIG["title"], className="text-center my-4"),
                    html.Hr()
                ])
            ]),
            
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