from pathlib import Path
from itertools import product
from math import comb
from collections import defaultdict
import csv, argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parent
RATES=(.983,.717,.302,0.) # G, F, P, N; N unknown, sensitivity separately

def read(name):
    with (ROOT/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(name, rows):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def choose(n,k): return comb(n,k) if 0<=k<=n else 0

def mixture(k,nrate=0.,grate=.983):
    rates=(grate,.717,.302,nrate)
    for bits in product((0,1),repeat=4):
        weight=np.prod([p if b else 1-p for b,p in zip(bits,rates)])
        if weight: yield (bits[0],bits[1]*k,bits[2]*k,bits[3]*k),float(weight)

def transform(c,policy):
    g,f,p,n=c; a=[0,f,p,n]; freed=g
    if policy=='keep':return c
    if policy=='ban_other':return tuple(a)
    order={'ban_F':(1,), 'ban_FPN':(1,2,3),'ban_N':(3,),'ban_P':(2,)}[policy]
    for i in order:
        add=min(freed,3-a[i]); a[i]+=add;freed-=add
    return tuple(a)

def distribution(mix,policy,size=40):
    out=defaultdict(float)
    for c,w in mix:
        c=transform(c,policy); other=size-sum(c)
        for h in product(*(range(x+1) for x in c)):
            if sum(h)>5:continue
            prob=choose(other,5-sum(h))
            for x,y in zip(c,h):prob*=choose(x,y)
            out[h]+=w*prob/comb(size,5)
    assert abs(sum(out.values())-1)<1e-10
    return dict(out)

def draws(r):
    normal,hand,deck,extra,grave,banish=[int(r[k]) for k in ['normal','hand_ss','deck_ss','extra_ss','grave_ss','banish_ss']]
    return (hand+deck+extra+grave+banish,deck+extra,normal+hand,grave+banish)

def evaluate(h,d,board,neg,mode):
    # Deterministic route-aware potential: activate G if useful and up to two charmies ranked by gross draws.
    # Single-effect variant chooses strongest one across names. All attempts before all summons.
    g=[d[0]] if h[0] and d[0] else []
    ch=sorted([x for i in range(1,4) if d[i] for x in [d[i]]*h[i]],reverse=True)[:2]
    if mode=='single':
        options=[(d[i], i!=0) for i in range(4) if h[i] and d[i]]
        if not options:return (0,0,0,0,0)
        val,isc=max(options,key=lambda x:(x[0],not x[1])); effects=[(val,isc)]
    else:effects=[(x,False) for x in g]+[(x,True) for x in ch]
    return evaluate_effects(effects,board,neg)

def evaluate_effects(effects,board,neg):
    effects=sorted(effects,key=lambda x:(x[0],not x[1]),reverse=True)
    attempts=len(effects); live=effects[neg:]; gross=sum(x[0] for x in live)
    before=5-attempts+gross
    after=min(before,board+6) if any(x[1] for x in live) else before
    return (int(gross>=1),int(after>5),gross,before-5,after-5)

def optimal(h,d,board,pneg):
    # Know the fixed route and probability of a counter, not whether the opponent holds it.
    # Allow holding all cards; maximize expected end-phase net, then gross, then fewer attempts.
    best=None; bestval=None
    for a in product(*(range(min(x,1 if i==0 else 2)+1) if d[i] else range(1) for i,x in enumerate(h))):
        if sum(a[1:])>2:continue
        effects=[(d[i],i!=0) for i in range(4) for _ in range(a[i])]
        v=(1-pneg)*np.array(evaluate_effects(effects,board,0))+pneg*np.array(evaluate_effects(effects,board,1))
        key=(round(v[4],12),round(v[2],12),-sum(a))
        if best is None or key>best: best,bestval=key,v
    return bestval

def lookup(dist,d,board,neg,mode):
    return np.array([evaluate(h,d,board,neg,mode) for h in dist],dtype=float)

POLICIES=['keep','ban_other','ban_F','ban_FPN','ban_N','ban_P']
METRICS=['coverage','positive_net','gross','net_before','net_after']

def main(trials):
    routes=read('routes.csv'); profiles=read('deck_profiles.csv'); rows=[]; route_rows=[]; overlap=[]; mcrows=[]
    for r in routes:
        d=draws(r); route_rows.append(dict(id=r['id'],theme=r['theme'],route=r['route'],G=d[0],F=d[1],P=d[2],N=d[3],board=r['board'],G_end_net=d[0]-1,F_end_net=min(4+d[1],int(r['board'])+6)-5,P_end_net=min(4+d[2],int(r['board'])+6)-5,N_end_net=min(4+d[3],int(r['board'])+6)-5))
    scenarios=[(f'usage_k{k}_N{int(nr*100)}',list(mixture(k,nr)),40) for k in (1,2,3) for nr in (0,.2,.5)]
    scenarios += [(p['id'],[(tuple(int(p[x]) for x in ('g','f','p','n')),1.)],int(p['size'])) for p in profiles]
    # Ash is once per turn; 94.8% adoption and 3 copies among adopters; sensitivity, not observed use rate.
    ash=.948*(1-comb(37,5)/comb(40,5))
    rng=np.random.default_rng(2026112703)
    for name,mix,size in scenarios:
        for pol in POLICIES:
            dist=distribution(mix,pol,size); weights=np.array(list(dist.values()))
            overlap.append(dict(scenario=name,policy=pol,any_hold=sum(w for h,w in dist.items() if sum(h)),charmy_hold=sum(w for h,w in dist.items() if sum(h[1:])),two_charmy_hold=sum(w for h,w in dist.items() if sum(h[1:])>=2)))
            sample=None
            if name=='usage_k3_N0':
                # Multinomial draws over the exact opening-hand state probabilities.
                sample=rng.multinomial(trials,weights/weights.sum())/trials
            for r in routes:
                d=draws(r); board=int(r['board'])
                for mode in ['single','stack']:
                    a=lookup(dist,d,board,0,mode); b=lookup(dist,d,board,1,mode)
                    for counter,pneg in [('none',0.),('ash',ash),('always_one',1.)]:
                        vals=(1-pneg)*a+pneg*b
                        res=weights@vals
                        row=dict(scenario=name,policy=pol,route=r['id'],mode=mode,counter=counter,negation_prob=pneg,**dict(zip(METRICS,res)))
                        rows.append(row)
                        if sample is not None and mode=='stack' and counter=='ash':
                            # sample actual counter state conditional on each hand, from independently sampled hand state counts
                            counts=np.rint(sample*trials).astype(int); blocked=rng.binomial(counts,pneg)
                            mc=((counts-blocked)@a+blocked@b)/trials
                            mcrows.append(dict(policy=pol,route=r['id'],trials=trials,**{f'{m}_exact':v for m,v in zip(METRICS,res)},**{f'{m}_mc':v for m,v in zip(METRICS,mc)}))
    for name,mix,size in scenarios:
        for pol in POLICIES:
            dist=distribution(mix,pol,size); weights=np.array(list(dist.values()))
            for r in routes:
                for counter,pneg in [('none',0.),('ash',ash),('always_one',1.)]:
                    vals=np.array([optimal(h,draws(r),int(r['board']),pneg) for h in dist]); res=weights@vals
                    rows.append(dict(scenario=name,policy=pol,route=r['id'],mode='net_optimal',counter=counter,negation_prob=pneg,**dict(zip(METRICS,res))))
    write('candidate_draws.csv',[dict(draws=k,remaining_deck=35,candidates=c,probability=1-choose(35-c,k)/comb(35,k)) for c in (5,8) for k in range(13)]);write('route_draws.csv',route_rows);write('opening_overlap.csv',overlap);write('results.csv',rows);write('monte_carlo.csv',mcrows)
    try: font_manager.findfont('Noto Sans CJK JP',fallback_to_default=False);plt.rcParams['font.family']='Noto Sans CJK JP'
    except ValueError: pass
    plt.rcParams.update({'figure.dpi':160,'axes.spines.top':False,'axes.spines.right':False})
    labels=[r['id'] for r in routes]; x=np.arange(len(labels));fig,ax=plt.subplots(figsize=(9,4.4))
    for i,k in enumerate(['G','F','P','N']):ax.bar(x+(i-1.5)*.19,[r[k] for r in route_rows],.19,label=k)
    ax.set_xticks(x,labels);ax.set_ylabel('ドロー枚数');ax.legend(ncol=4);ax.set_title('召喚元別のドロー枚数（全召喚前に適用）');fig.tight_layout();fig.savefig(ROOT/'01_route_draws.png');plt.close(fig)
    sub=[r for r in rows if r['scenario']=='usage_k3_N0' and r['mode']=='stack' and r['counter']=='ash']; pols=['keep','ban_other','ban_F','ban_FPN','ban_N'];fig,ax=plt.subplots(figsize=(10,4.6))
    for i,p in enumerate(pols):ax.bar(x+(i-2)*.15,[100*next(r['coverage'] for r in sub if r['policy']==p and r['route']==z) for z in labels],.15,label=p)
    ax.set_xticks(x,labels);ax.set_ylabel('1枚以上ドローできる初手 (%)');ax.set_title('採用率モデル・うらら1回の無効を考慮');ax.legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(ROOT/'02_coverage.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.6))
    for i,p in enumerate(pols):ax.bar(x+(i-2)*.15,[next(r['net_after'] for r in sub if r['policy']==p and r['route']==z) for z in labels],.15,label=p)
    ax.set_xticks(x,labels);ax.set_ylabel('初手あたり平均純手札増減 (枚)');ax.set_title('エンドフェイズ調整・発動コスト込み');ax.axhline(0,color='gray',lw=.8);ax.legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(ROOT/'03_net.png');plt.close(fig)
    print('exact conditions',len(rows),'MC conditions',len(mcrows),'trials per policy',trials,'unique initial samples',trials*len(POLICIES),'ash probability',ash,'max coverage error pp',max(abs(r['coverage_exact']-r['coverage_mc'])*100 for r in mcrows))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--trials',type=int,default=1000000);main(ap.parse_args().trials)
