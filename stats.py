# from kin import KinClient, TEST_ENVIRONMENT, PROD_ENVIRONMENT
# import asyncio
# import requests

#
# async def d():
#     async with KinClient(PROD_ENVIRONMENT) as client:
#         account_data = await client.get_account_data('GB43PIR5AKNVBVKXACD3HOSJYGLIVXC7GWPRQZFA4YF2DK33KAGQCFAS')
#         return account_data
#
# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# response = loop.run_until_complete(d())
# print(response)

# account_id = 'GB43PIR5AKNVBVKXACD3HOSJYGLIVXC7GWPRQZFA4YF2DK33KAGQCFAS'
# data = []
# r = requests.get('https://horizon-block-explorer.kininfrastructure.com/accounts/{}/payments?limit=200&order=desc'.format(account_id))
# x = r.json()
# next_ = x['_links']['next']['href']
# l = x['_embedded']['records']
# while l:
#     for i in l:
#         # print(i)
#         type_ = i['type']
#         if type_ != 'payment':
#             source_account = i['source_account']
#             created_at = i['id']
#             starting_balance = i.get('starting_balance', -1)
#             funder = i.get('funder', '')
#             account = i.get('account', '')
#             from_ = i.get("from", "")
#             to_ = i.get("to", "")
#             amount = i.get('amount', -1)
#             data.append({'source_account': source_account, 'type': type_, 'created_at': created_at,
#                          'starting_balance': starting_balance, 'funder': funder, 'account': account,
#                          'from': from_, 'to_': to_, 'amount': amount})
#     r = requests.get(next_)
#     x = r.json()
#     next_ = x['_links']['next']['href']
#     l = x['_embedded']['records']
#
# del data[-129:]
#
# all = []
# for q in data:
#     account_id = q['account']
#     r = requests.get('https://horizon-block-explorer.kininfrastructure.com/accounts/{}/payments?limit=200&order=desc'.format(account_id))
#     x = r.json()
#     next_ = x['_links']['next']['href']
#     l = x['_embedded']['records']
#     for i in l:
#         print(i)
#         type_ = i['type']
#         if type_ != 'create_account':
#             source_account = i['source_account']
#             created_at = i['id']
#             starting_balance = i.get('starting_balance', -1)
#             funder = i.get('funder', '')
#             account = i.get('account', '')
#             from_ = i.get("from", "")
#             to_ = i.get("to", "")
#             amount = i.get('amount', -1)
#             all.append({'source_account': source_account, 'type': type_, 'created_at': created_at,
#                          'starting_balance': starting_balance, 'funder': funder, 'account': account,
#                          'from': from_, 'to_': to_, 'amount': amount})
#
# print(all)