from configparser import ConfigParser
import json
config = ConfigParser()
config.read("config.ini")

# InfluxDB
try:
    from influxdb import InfluxDBClient
    influxclient = InfluxDBClient(host=config['INFLUXDB']['host'], port=int(config['INFLUXDB']['port']), username=config['INFLUXDB']['username'], password=config['INFLUXDB']['password'], ssl=bool(config['INFLUXDB']['ssl']), verify_ssl=bool(config['INFLUXDB']['verify_ssl']))
    influxclient.create_database(config['INFLUXDB']['database'])
    influxclient.switch_database(config['INFLUXDB']['database'])
    enable_influxdb=True
except:
    enable_influxdb=False

#LocalBitcoin
hmac_key=config['LOCALBITCOINS']['hmac_key']
hmac_secret=config['LOCALBITCOINS']['hmac_secret']
lb_block=tuple(json.loads(config['LOCALBITCOINS']['lb_block']))

minspend=float(config['SPEND']['minspend'])

# Coinbase Configuration
# None required

# Oanda Configuration
access_token=config['OANDA']['access_token']

def lb2int(value):
    value=str(value)
    if(value=="null"):
        return 0.0
    value=value.replace("+","")
    value=value.replace(" ","")
    try:
        return float(value)
    except:
        return 0.0

try:
    from lbcapi.lbcapi import api
    conn = api.hmac(hmac_key, hmac_secret)
    ads_json = conn.call('GET', '/buy-bitcoins-online/cn/china/national-bank-transfer/.json').json()

    from tabulate import tabulate
    from termcolor import colored

    from oandapyV20 import API    # the client
    from oandapyV20.contrib.factories import InstrumentsCandlesFactory
    from oandapyV20.endpoints import pricing, accounts
    client = API(access_token=access_token)
    instr="USD_CNH"
    gran="H4"
    params = {
        "granularity": gran,
        "count": 1
    }

    r= accounts.AccountList()
    account_id = (client.request(r))['accounts'][0]['id']
    r=pricing.PricingInfo(account_id,params={"instruments": instr})
    rv= client.request(r)
    askprice=float(rv['prices'][0]['asks'][0]['price'])
    bidprice=float(rv['prices'][0]['bids'][0]['price'])

    import cbpro
    public_client = cbpro.PublicClient()
    coinbaselast=public_client.get_product_ticker(product_id='BTC-USD')
    coinbaseprice=float(coinbaselast['price'])
    pricetime=coinbaselast['time']

    for ad in ads_json['data']['ad_list']:
        lb_username=ad['data']['profile']['username']
        lb_tradecount=lb2int(ad['data']['profile']['trade_count'])
        lb_feedback_score=ad['data']['profile']['feedback_score']
        lb_min_amount=round(lb2int(ad['data']['min_amount']),2)
        lb_max_amount=round(lb2int(ad['data']['max_amount_available']),2)
        lb_temp_price=round(float(ad['data']['temp_price']),2)
        lb_public_view=ad['actions']['public_view']
        if(lb_tradecount>10 and lb_max_amount>=minspend and lb_feedback_score>=97 and lb_username not in lb_block):
            #print(lb_username,lb_tradecount,lb_feedback_score,lb_min_amount,lb_max_amount,lb_temp_price,lb_public_view)
            coinbasepricermb=coinbasepricermb=round(coinbaseprice*askprice*1.005,2)
            lb_temp_price_usd=round(lb_temp_price/bidprice,2)
            profit=round(coinbasepricermb-lb_temp_price,2)
            percentprofit=round(profit/coinbasepricermb*100,2)
            datapoint = [{   "time" : pricetime ,
                        "measurement" : "localbitcoins",
                        "fields": {
                        "USDRMB-ask": askprice ,
                        "USDRMB-bid": bidprice ,
                        "Coinbase-USD": coinbaseprice ,
                        "Coinbase-RMB": coinbasepricermb ,
                        "LB-RMB": lb_temp_price ,
                        "LB-USD": lb_temp_price_usd ,
                        "Profit-RMB": profit ,
                        "Percent-Profit": percentprofit ,
                        "User": lb_username ,
                        "Min-RMB": lb_min_amount ,
                        "Max-RMB": lb_max_amount
                        }
                    }]
            table=[["Time",pricetime],["USD-RMB ask",askprice],["USD-RMB bid",bidprice],["Coinbase Price USD",coinbaseprice],["Coinbase Price RMB",coinbasepricermb],["LB Price RMB",lb_temp_price],["LB Price USD",lb_temp_price_usd],["Profit RMB",colored(profit,'red' if profit<0 else 'green')],["Percent Profit",colored(percentprofit,'red' if percentprofit<0 else 'green')],["Offer",lb_public_view],["Username",lb_username],["Min RMB",lb_min_amount],["Max RMB",lb_max_amount]]
            print(tabulate(table,tablefmt="fancy_grid"))
            if(enable_influxdb):
                influxclient.write_points(datapoint)
            break
except Exception as e:
    print("ERROR",e)

