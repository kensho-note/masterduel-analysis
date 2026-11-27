"""Conditional fixed-board paired model. Not a duel/win-rate simulator."""
import argparse,csv,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
P=Path(__file__).resolve().parent

def read(name):
    with (P/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
def write(name,rows):
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def miss(N,K,n):
    assert 0<=n<=N and 0<=K<=N
    return math.comb(N-K,n)/math.comb(N,n) if n<=N-K else 0.
def exact(N,K,h,k):
    b=1-miss(N,K,h); t=1-miss(N,K,h+k)
    return b,t,t-b, (t-b)/(1-b) if b<1 else 0.,1-miss(N,K,k)

def main(trials):
    rng=np.random.default_rng(2026112704)
    results=[]; checkpoints=[]; grid=[]; maxerr=0
    for p in read('profiles.csv'):
        d={k:int(p[k]) for k in ['deck_size','fixed_open','fixed_deck','ash','veiler','droll','nibiru','imperm','g_cap']}
        N=d['deck_size']-d['fixed_open']-d['fixed_deck']; h=5-d['fixed_open']; deck=N-h
        for group,K in [('ash_veiler',d['ash']+d['veiler']),('droll',d['droll']),('nibiru',d['nibiru'])]:
            held=rng.hypergeometric(K,N-K,h,size=trials) if K else np.zeros(trials,dtype=int)
            left=K-held; drawn=np.zeros(trials,dtype=int)
            for k in range(11):
                if k:
                    hit=rng.random(trials)<left/(deck-k+1); left=left-hit;drawn+=hit
                b,t,delta,conditional,draw_any=exact(N,K,h,k)
                mc_b=np.mean(held>0);mc_t=np.mean(held+drawn>0);mc_delta=np.mean((held==0)&(drawn>0))
                maxerr=max(maxerr,abs(mc_delta-delta),abs(mc_b-b),abs(mc_t-t))
                row=dict(profile=p['profile'],group=group,pool=N,unknown_hand=h,remaining_deck=deck,candidates=K,draws=k,baseline=b,with_g=t,increment=delta,increment_given_no_held=conditional,draw_any=draw_any,mc_baseline=mc_b,mc_with_g=mc_t,mc_increment=mc_delta,trials=trials)
                results.append(row)
                if (group,k) in [('ash_veiler',1),('ash_veiler',3),('droll',1),('nibiru',4)]:checkpoints.append({**row,'checkpoint':{('ash_veiler',1):'Sword search',('ash_veiler',3):'Duo search',('droll',1):'after Sword search',('nibiru',4):'5 monsters incl normal'}[(group,k)]})
    for N in [25,30,35,40]:
        for K in [1,3,5,8]:
            for h in [0,2,3]:
                for k in range(11):
                    b,t,delta,conditional,da=exact(N,K,h,k)
                    for q in [.25,.5,.75,1.]:
                        grid.append(dict(pool=N,candidates=K,unknown_hand=h,draws=k,gate_relevance_assumed=q,baseline=b,with_g=t,increment=delta,conditional_increment=conditional,proxy_increment=q*delta))
    write('results.csv',results);write('checkpoints.csv',checkpoints);write('sensitivity.csv',grid)
    if any('Noto Sans CJK JP'==f.name for f in font_manager.fontManager.ttflist):plt.rcParams['font.family']='Noto Sans CJK JP'
    fig,ax=plt.subplots(figsize=(9,5))
    for name in ['R2','R3','D2']:
        rr=[r for r in results if r['profile']==name and r['group']=='ash_veiler'];ax.plot([r['draws'] for r in rr],[100*r['increment'] for r in rr],marker='o',label=name)
    ax.set(xlabel='増Gによる追加ドロー枚数',ylabel='新たに妨害候補を持つ確率（pt）',title='先攻の初期手札に候補がないケースからの増加');ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(P/'01_increment.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5)); labels=['R2','R3','D2']; x=np.arange(3); rr=[next(r for r in results if r['profile']==name and r['group']=='ash_veiler' and r['draws']==1) for name in labels];ax.bar(x-.18,[100*r['baseline'] for r in rr],.36,label='増Gなし（非候補枠）');ax.bar(x+.18,[100*r['with_g'] for r in rr],.36,label='増G適用・1ドロー');ax.set_xticks(x,labels);ax.set(ylabel='うらら・ヴェーラー保有率（%）',title='ソードのサーチ直前：同じ盤面・同じ初期手札');ax.legend();ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(P/'02_sword_gate.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));rr=[r for r in grid if r['pool']==35 and r['unknown_hand']==3 and r['gate_relevance_assumed']==1.]
    for K in [1,3,5,8]:
        r2=[r for r in rr if r['candidates']==K];ax.plot([r['draws'] for r in r2],[100*r['increment'] for r in r2],marker='o',label=f'候補{K}枚')
    ax.set(xlabel='追加ドロー枚数',ylabel='新たな妨害候補保有の増加（pt）',title='感度分析：候補枚数による違い（未知35枚・手札3枚）');ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(P/'03_sensitivity.png',dpi=160);plt.close(fig)
    print(f'profiles=3 groups=3 MC trajectories={9*trials:,} exact marginal rows={len(results)} sensitivity rows={len(grid)} max error={maxerr*100:.5f} pp')
    for r in checkpoints:
        print(r['profile'],r['checkpoint'],*(f'{100*r[k]:.3f}' for k in ['baseline','with_g','increment','increment_given_no_held']))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--trials',type=int,default=1000000);main(a.parse_args().trials)
