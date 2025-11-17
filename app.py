import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from babel.numbers import format_currency
import re
from datetime import timedelta
import streamlit as st

def iter_rows(table):
    obj = {}
    for row in table.find_all('tr'):
        key, val = [data.string for data in row.find_all('td')]
        key = re.sub(r'\W', '', re.sub(r' ', '_', key)).lower()
        if key in obj:
            yield obj
            obj = {}
        obj[key] = val
    yield obj


@st.cache_data(ttl=300)
def fetch_transactions(card_number):
    r = requests.get('https://farepay.rideuta.com/cardActivity.html',params={
        'cardNum': card_number,
    })
    return r.text

st.title("UTA Card Transactions")
if not st.query_params.get("card"):
    card_number = st.text_input("Enter your UTA Card Number", value=st.query_params.get("card"))
    if not card_number:
        st.stop()
else:
    card_number = st.query_params.get("card")

with st.spinner("Fetching transactions..."):
    html = fetch_transactions(card_number)

soup = BeautifulSoup(html)

balance_table = soup.find(class_='basicTable')
if not balance_table:
    st.error("Could not find transactions. Please check your card number.")
    st.stop()

if not st.query_params.get("card"):
    st.query_params["card"] = card_number

BALANCE = float(re.sub(r'\$', '', next(iter_rows(balance_table))['balance']))
st.metric("Current Balance", format_currency(BALANCE, currency='USD'))

df = (
    pd.DataFrame(iter_rows(soup.find(id='table')))
    .drop_duplicates(subset=['transaction_id'])
    .query('note == "Success"')
    [['date','amount']]
)
df['time'] = pd.to_datetime(df.date)
# If it happend at midnight, pretend it happened the day before
df['time'] = (df.time - timedelta(hours=1)).apply(lambda ts: ts.replace(minute=59)).where(df.time.dt.hour == 0, df.time)
df['date'] = df.time
date = df.time.dt.date
df['_group'] = (date != date.shift()).cumsum()
df['amount'] = df.amount.str.replace('$','').astype(float)
df['balance'] = ((-df.amount).cumsum() + BALANCE).shift(fill_value=BALANCE)

def color_groups(row):
    if row['_group'] % 2 == 0:
        return ['background-color: #f0f0f0'] * len(row)
    else:
        return ['background-color: white'] * len(row)

st.dataframe(
    (
        df.query('amount < 0')
        [['date', 'time', 'balance', '_group']]
        .sort_values('time', ascending=False)
        .style.apply(color_groups, axis=1)
    ),
    height=800,
    hide_index=True,
    column_config={
        'date': st.column_config.DateColumn(
            "Date",
            # width="medium",
            format="ddd, MMM Do",
            help="The date the transaction occurred.",
        ),
        'time': st.column_config.TimeColumn(
            "Time",
            # width="small",
            format="h:mm a",
            help="The time the transaction occurred.",
        ),
        'balance': st.column_config.NumberColumn(
            "Balance",
            format="dollar",
            help="The balance on the card after the transaction.",
        ),
        '_group': None,
    }
)
        