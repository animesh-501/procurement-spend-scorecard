# Data

**Source:** USAID Supply Chain Management System (SCMS) "Supply Chain Shipment Pricing Data", published as US government open data ([dataset page](https://data.amerigeoss.org/dataset/supply-chain-shipment-pricing-data)).

`raw/SCMS_Delivery_History_Dataset_20150929.csv`: 10,324 purchase lines of health commodities (medicines and test kits) shipped 2006–2015, with vendor, item, quantity, pack price, delivery terms, shipment mode, freight, and scheduled vs. actual delivery dates.

Latin-1 encoded; `src/data.py` handles that.
