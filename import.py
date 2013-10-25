# -*- coding: utf-8 -*-
import predictionio
from lxml.etree import parse
import urllib2
import os, difflib
from pprint import pprint
from unidecode import unidecode

client = predictionio.Client(appkey="mKtl95U5lSKmMJgeMbOG6MQUkxFyRGOksyGdoLu3YQtmIY3hOYpp5Q6s8tIEy5ch")


def urlopenC(url):
    headers = { 'User-Agent' : 'Mozilla/5.0' }
    req = urllib2.Request(url, None, headers)
    xml = urllib2.urlopen(req)
    return xml

def getUsers():
    soup = parse('data/deputados.xml').getroot()
    users = []
    for d in soup.xpath('//deputado'):
        deputado = {
            'pio_uid' : d.xpath('./idParlamentar')[0].text,
            'nome' : d.xpath('./nome')[0].text,
            'nome_parlamentar' : d.xpath('./nomeParlamentar')[0].text,
            'partido' : d.xpath('./partido')[0].text,
            'sexo' : d.xpath('./sexo')[0].text,
            'uf' : d.xpath('./uf')[0].text,
        }
        users.append(deputado)
    return users

def getItems():
    soup = parse('data/votacoes2013.xml').getroot()
    items = []
    for i in soup.xpath("//proposicao"):
        proposicao = {
            'pio_iid' : i.xpath('./codProposicao')[0].text,
            'tipo' : i.xpath('./nomeProposicao')[0].text.split()[0],
            'numero' : i.xpath('./nomeProposicao')[0].text.split()[1].split('/')[0],
            'ano' : i.xpath('./nomeProposicao')[0].text.split()[1].split('/')[1]
        }
        proposicao['pio_itypes'] = [proposicao['tipo']]
        if len(i.xpath('./nomeProposicao')[0].text.split()[0]) == 2: #hack para proposicoes tipo REQ 8/2013 PEC09011 => PEC 90/2011
            proposicao = getIndexacao(proposicao)
            items.append(proposicao)
    return items

def getIndexacao(p):
    fileurl = 'data/proposicoes/' + p['tipo'] +'-'+p['numero']+'-'+p['ano']+'.xml'
    if os.path.isfile(fileurl):
        soup = parse(fileurl).getroot()
    else:
        print "Dowloading Index " + fileurl
        downloadIndexacao(p, fileurl)
        soup = parse(fileurl).getroot()
    p['pio_itypes'] += [t.strip() for t in soup.xpath("//proposicao/Indexacao")[0].text.split(',')]
    p['autor'] = [a.strip() for a in soup.xpath("//proposicao/Autor")[0].text.split(',')]
    return p

def getVotacoes(p):
    fileurl = 'data/votacoes/' + p['tipo'] +'-'+p['numero']+'-'+p['ano']+'.xml'
    if os.path.isfile(fileurl):
        soup = parse(fileurl).getroot()
    else:
        print "Dowloading Votacao " + fileurl
        if downloadVotacoes(p, fileurl):
            soup = parse(fileurl).getroot()
        else:
            return []
    votacoes = []
    for vt in soup.xpath("//Votacao"):
        votos = []
        for v in vt.xpath("./votos/Deputado"):
            voto = {
                'nome' : v.get('Nome'),
                'acao' : v.get('Voto'),
                'partido' : v.get('Partido'),
                'uf' : v.get('UF')
            }
            votos.append(voto)
        votacoes.append(votos)
    return votacoes

def downloadVotacoes(p, fileurl):
    url = 'http://www.camara.gov.br/SitCamaraWS/Proposicoes.asmx/ObterVotacaoProposicao?tipo='+p['tipo']+'&numero='+p['numero']+'&ano='+p['ano']
    try:
        soup = urlopenC(url).read()
    except:
        print 'error on ' + url
        return False
    with open(fileurl, 'w') as xml:
        xml.write(soup)
    return True

def downloadIndexacao(p, fileurl):
    url = 'http://www.camara.gov.br/SitCamaraWS/Proposicoes.asmx/ObterProposicao?tipo='+p['tipo']+'&numero='+p['numero']+'&ano='+p['ano']
    try:
        soup = urlopenC(url).read()
    except:
        print 'error on ' + url
        return False
    with open(fileurl, 'w') as xml:
        xml.write(soup)
    return True

def findUser(v, users):
    user_id = None
    possiveis = []
    for u in users:
        if v['uf'] == u['uf']:
            possiveis.append(u['nome_parlamentar'])
    best_match = difflib.get_close_matches(v['nome'].upper(), possiveis, n=1)
    if best_match:
        for u in users:
            if u['nome_parlamentar'] == best_match[0]:
                user_id = u['pio_uid']                 
    return user_id

def findItem(i, items):
    item_id = None
    for item in items:
        if i['tipo'] == item['tipo'] and i['ano'] == item['ano'] and i['numero'] == item['numero']:
            item_id = item['pio_iid']
            return item_id

def findAction(v):
    if v['acao'] == 'Sim':
        return 'like'
    elif v['acao'] == u'Não':
        return 'dislike'
    else:
        return 'view'

def getActions(users, items):
    actions = []
    for i in items:
        votacoes_pl = getVotacoes(i)
        for votacoes in votacoes_pl:
            for u in votacoes:
                behavior = {
                    'pio_uid' : findUser(u, users),
                    'pio_iid' : findItem(i, items),
                    'pio_action' : findAction(u)
                }
                actions.append(behavior)
    return actions


def rockandroll():
    users = getUsers()
    items = getItems()
    actions = getActions(users, items)
    print "Creating users..."
    for u in users:
        pprint(u)
        pio_uid = u['pio_uid']
        del u['pio_uid']
        client.create_user(pio_uid, u)

    print "Creating items..."
    for i in items:
        pio_iid = i['pio_iid']
        pio_itypes = tuple(i['pio_itypes'])
        del i['pio_iid']
        del i['pio_itypes']
        client.create_item(pio_iid, pio_itypes, i)

    print "Creatim actions..."
    for a in actions:
        if a['pio_uid'] and a['pio_iid']:
            client.identify(a['pio_uid'])
            client.record_action_on_item(a['pio_action'], a['pio_iid'], {})