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
card_number = st.text_input("Enter your UTA Card Number", value=st.query_params.get("card"))
if not card_number:
    st.stop()

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
df['amount'] = df.amount.str.replace('$','').astype(float)
df['balance'] = ((-df.amount).cumsum() + BALANCE).shift(fill_value=BALANCE)

st.dataframe(
    df[['date', 'time','amount','balance']].sort_values('time', ascending=False),
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
        'amount': st.column_config.NumberColumn(
            "Amount",
            width='medium',
            format="dollar",
            help="The amount of the transaction. Negative values indicate money spent.",
        ),
        'balance': st.column_config.NumberColumn(
            "Balance",
            format="dollar",
            help="The balance on the card after the transaction.",
        ),
    }
)
        