aliexpress case: 1143803128134365
Un dispositivo di Ventilazione Meccanica Controllata (da ora anche VMC) ha 3 Modalità di trattamento dell'aria:
- Estiva: Modalità operativa automatica per il raffrescamento e la deumidificazione.
- Invernale: Modalità operativa automatica per il riscaldamento e la gestione dell'umidità.
- Mezza Stagione: Modalità operativa manuale per il raffrescamento, riscaldamento e la gestione dell'umidità.

Nelle modalità di funzionamento automatico ("Estiva" e "Invernale") la VMC utilizza i parametri di "Set Point", i "Flag" ed i "Sensori" per applicare il trattamento ("raffrescamento", "riscaldamento", "deumidificazione") opportuno. Nella modalità "Manuale" il trattamento deve essere gestito dal software stesso.

Il dispositivo VMC operante con i trattamenti automatici ("Estiva", "Invernale") può essere comandato attraverso i seguenti componenti del sistema:

    - Device Power
        Descrizione: Permette l’accensione e lo spegnimento del dispositivo.
        Tipo componente: Switch
        Valori: ON, OFF

    - Season Switch
            Descrizione: Permette di selezionare la modalità trattamento da utilizzare ("Estiva", "Invernale", "Mezza Stagione").
            Tipo componente: Switch
            Valori: Winter, Summer, Middle Season

    - Compressor Management
            Descrizione: Imposta la modalità operativa del compressore (solo per le modalità di trattamento "Estiva", "Invernale").
                Cooling Only: Il compressore produce solo aria fredda senza deumidificare.
                Dehumidification Only: Il compressore opera solo in deumidificazione.
                Cooling or Dehumidification: Il compressore opera in entrambe le modalità.
            Tipo componente: Switch
            Valori: "Cooling Only", "Dehumidification Only", "Cooling or Dehumidification"

    - Cooling Management
            Descrizione: Imposta l’alimentazione per il raffreddamento (solo per le modalità di trattamento "Estiva", "Invernale").
                Compressor only: Utilizza solo il compressore per produrre aria fredda.
                Water only: Utilizza solo la temperatura dell’acqua per produrre aria fredda.
                Water Else Compressor: Utilizza prima la temperatura dell’acqua e, se insufficiente, il compressore.
            Tipo componente: Switch
            Valori: Compressor only, Water only, Water Else Compressor

    - Recirculation Vent
            Descrizione: Permette il ricircolo dell’aria all’interno dell’appartamento senza prenderla dall’esterno.
            Tipo componente: Switch
            Valori: ON, OFF

    - Dew Point Management
            Descrizione: Seleziona la modalità di calcolo del dew point (punto di rugiada). Deve essere sempre impostata a "Fixed"
            Tipo componente: Switch
            Valori: Fixed, Variable

    - Spare Number
            Descrizione: Imposta la velocità di ventilazione.
            Tipo componente: Set Point
            Valori: Da 1 a 5, dove 5 è la velocità più elevata.

    - Ambient Temperature
            Descrizione: Imposta la temperatura target desiderata.
            Tipo componente: Set Point
            Valori: Da -10 a 40 °C.

    - Ambient Humidity
            Descrizione: Imposta la percentuale di umidità desiderata.
            Tipo componente: Set Point
            Valori: Da 0 a 100%.

    - Dew Point Temperature
            Descrizione: Imposta il valore del dew point sopra il quale la macchina in automatico attiva la deumidificazione.
            Tipo componente: Set Point
            Valori: Da 10 a 30 °C.

In aggiunta il dispositivo VMC dispone dei seguenti Indicatori e Sensori read-only

    - Compressor 
            Descrizione: Indicatore read-only che il compressore è attivo.
            Tipo componente: Flag
            Valori: ON, OFF

    - Free Cooling
            Descrizione: Indicatore read-only che il Free Cooling è attivo.
            Tipo componente: Flag
            Valori: ON, OFF

    - Plant Water Request
            Descrizione: Indicatore read-only che la macchina sta richiedendo la circolazione di acqua per operare.
            Tipo componente: Flag
            Valori: ON, OFF

    - Heating Request
            Descrizione: Indicatore read-only che la macchina richiede riscaldamento per raggiungere la temperatura impostata.
            Tipo componente: Flag
            Valori: ON, OFF

    - Cooling Request
            Descrizione: Indicatore read-only che la macchina richiede raffrescamento per raggiungere la temperatura impostata.
            Tipo componente: Flag
            Valori: ON, OFF

    - Dehumidification
            Descrizione: Indicatore read-only che la macchina ha necessità di deumidificare per raggiungere l’umidità impostata o restare sotto il dew point.
            Tipo componente: Flag
            Valori: ON, OFF

    - Dew Point Alarm
            Descrizione: Indicatore read-only che c’è un problema di condensa e che è necessario deumidificare.
            Tipo componente: Flag
            Valori: ON, OFF

    - Water Temperature
            Descrizione: Sensore read-only che indica la temperatura dell’acqua nella macchina.
            Tipo componente: Sensor
            Valori: Da 0 a 40 °C.

    - Ambient Temperature
            Descrizione: Sensore read-only che indica la temperatura dell’ambiente.
            Tipo componente: Sensor
            Valori: Da 0 a 40 °C.

    - Ambient Humidity
            Descrizione: Sensore read-only che indica la percentuale di umidità dell’ambiente.
            Tipo componente: Sensor
            Valori: Da 0 a 100%.

    - Ambient Outdoor Temperature
            Descrizione: Sensore read-only che indica la temperatura esterna all’ambiente.
            Tipo componente: Sensor
            Valori: Da 0 a 40 °C.

Note sui Componenti

    Gli switch sono componenti che possono essere azionati per far compiere alla macchina delle azioni.
    I set point sono registri read-only impostati dall’utente che possono essere letti e valutati dal sistema di controllo.
    I flag sono indicatori ON/OFF read-only che possono essere letti e valutati dal sistema di controllo.
    I sensori sono indicatori read-only che possono essere letti e valutati dal sistema di controllo.

Agendo come un ingegnere informatico con esperienze di sistemi di controllo:
realizzare un software di controllo per la VMC quando opera attraverso le modalità di trattamento "Estiva", "Invernale". Il software deve essere scritto in python e deve utilizzare una rete neurale adattiva che valuta tutti i componenti disponibile: "Switch", "Set Point", "Flag" e "Sensori". I dati di questi componenti sono disponibili su Influxdb con una profondità storica di 30 giorni.

<code>
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM
from influxdb_client import InfluxDBClient

# Configurazione di InfluxDB
bucket = "your_bucket"
org = "your_org"
token = "your_token"
url = "http://localhost:8086"

# Connessione a InfluxDB
client = InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

# Query per ottenere i dati storici
def get_data_from_influxdb():
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "vmc_data")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    result = query_api.query_data_frame(org=org, query=query)
    result.drop(columns=['result', 'table', '_start', '_stop', '_time'], inplace=True)
    return result


import "contrib/anaisdg/statsmodels"
// v.bucket, v.timeRangeStart, and v.timeRange stop are all variables supported by the flux plugin and influxdb

data = from(bucket: v.bucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "°C")
  |> filter(fn: (r) =>  r["entity_id"] =~ /^ambient(.*)/)
  |> filter(fn: (r) =>  r["entity_id"] !~ /outdoor(.*)/ and r["entity_id"] !~ /electric(.*)/)
  //|> filter(fn: (r) =>  r["entity_id"] !~ /living(.*)/ and r["entity_id"] !~ /guest(.*)/)
  |> filter(fn: (r) => r["_field"] == "value")
  |> group(columns: ["_measurement"], mode:"by")

averaged_data = data
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
  //|> mean()
  |> yield(name: "single_avg")
//data
//  |> aggregateWindow(every: 5m, fn: min, createEmpty: false)
//    |> yield(name: "single_av")

// Aggiungi una trendline (regressione lineare) ai dati mediati
trendline = averaged_data   
  |> statsmodels.linearRegression()
  //|> map(fn: (r) => ({ r with _value: r.y_hat }))
  |> map(fn: (r) => ({ _time: r._time, _value: r.y_hat }))  // Map to get the predicted values
  |> yield(name: "trendline")


data = get_data_from_influxdb()

# Separazione delle caratteristiche (features) e delle etichette (labels)
features = data.drop(columns=['Ambient Temperature Sensor', 'Ambient Humidity Sensor']).values
labels = data[['Ambient Temperature Sensor', 'Ambient Humidity Sensor']].values

# Normalizzazione dei dati
scaler_features = MinMaxScaler(feature_range=(0, 1))
scaler_labels = MinMaxScaler(feature_range=(0, 1))

features_scaled = scaler_features.fit_transform(features)
labels_scaled = scaler_labels.fit_transform(labels)

# Pre-elaborazione per la rete neurale
X_train = np.reshape(features_scaled, (features_scaled.shape[0], features_scaled.shape[1], 1))
y_train = labels_scaled

# Definizione della rete neurale
model = Sequential()
model.add(LSTM(50, return_sequences=True, input_shape=(X_train.shape[1], 1)))
model.add(LSTM(50, return_sequences=False))
model.add(Dense(25))
model.add(Dense(y_train.shape[1]))

model.compile(optimizer='adam', loss='mean_squared_error')

# Addestramento del modello
model.fit(X_train, y_train, batch_size=1, epochs=1)

# Funzione per il controllo della VMC
def control_vmc(input_data):
    input_data_scaled = scaler_features.transform(input_data)
    input_data_reshaped = np.reshape(input_data_scaled, (input_data_scaled.shape[0], input_data_scaled.shape[1], 1))
    predictions = model.predict(input_data_reshaped)
    return scaler_labels.inverse_transform(predictions)

def execute_control_actions(predictions, current_state):
    temp, hum = predictions[0]
    actions = {}

    # Logica per il controllo della temperatura
    if temp < current_state['Ambient Temperature Set Point']:
        actions['Device Power Switch'] = 'ON'
        actions['Season Switch'] = 'Winter'
    elif temp > current_state['Ambient Temperature Set Point']:
        actions['Device Power Switch'] = 'ON'
        actions['Season Switch'] = 'Summer'
    else:
        actions['Device Power Switch'] = 'ON'
        actions['Season Switch'] = 'Middle Season'
    
    # Logica per il controllo dell'umidità
    if hum < current_state['Ambient Humidity Set Point']:
        actions['Dehumidification Flag'] = 'OFF'
    elif hum > current_state['Ambient Humidity Set Point']:
        actions['Dehumidification Flag'] = 'ON'
    else:
        actions['Dehumidification Flag'] = 'OFF'

    # Gestione del dew point alarm
    if current_state['Dew Point Alarm Flag'] == 'ON':
        actions['Dehumidification Flag'] = 'ON'

    # Logica per la ventilazione del ricircolo
    if current_state['Recirculation Vent Switch'] == 'ON':
        actions['Recirculation Vent Switch'] = 'ON'
    else:
        actions['Recirculation Vent Switch'] = 'OFF'

    return actions

# Esempio di utilizzo del modello per prendere decisioni di controllo
current_state = {
    'Device Power Switch': 'OFF',
    'Season Switch': 'Middle Season',
    'Compressor Management Switch': 'Cooling Only',
    'Cooling Management Switch': 'Compressor only',
    'Recirculation Vent Switch': 'OFF',
    'Dew Point Management Switch': 'Fixed',
    'Spare Set Point': 3,
    'Ambient Temperature Set Point': 22,
    'Ambient Humidity Set Point': 50,
    'Dew Point Temperature Set Point': 15,
    'Compressor Flag': 'OFF',
    'Free Cooling Flag': 'OFF',
    'Plant Water Request Flag': 'OFF',
    'Heating Request Flag': 'OFF',
    'Cooling Request Flag': 'OFF',
    'Dehumidification Flag': 'OFF',
    'Dew Point Alarm Flag': 'OFF',
    'Water Temperature Sensor': 20,
    'Ambient Temperature Sensor': 22,
    'Ambient Humidity Sensor': 50,
    'Ambient Outdoor Temperature Sensor': 10
}

new_data = np.array([[1, 'Winter', 'Cooling Only', 'Compressor only', 0, 'Fixed', 3, 22, 50, 15, 0, 0, 0, 0, 0, 0, 0, 20, 22, 50, 10]])
control_actions = control_vmc(new_data)
actions = execute_control_actions(control_actions, current_state)
print(actions)

client.close()


</code>


