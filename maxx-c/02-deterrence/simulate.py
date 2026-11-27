import argparse,csv,math,pathlib
import numpy as np
from opening_model import current,exact,sim
P=pathlib.Path(__file__).resolve().parent
C=math.comb

def write(name,rows):
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def read(name):
    with (P/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def getprob(N,g,m,k):
    # Conditional on >=1 G in the 5-card hand; m candidate cards distinct from G.
    den=C(N,5)-C(N-g,5)
    if not den:return 0,0
    pnew=pfresh=0
    for x in range(1,min(g,5)+1):
        for y in range(min(m,5-x)+1):
            z=5-x-y
            if not 0<=z<=N-g-m:continue
            w=C(g,x)*C(m,y)*C(N-g-m,z)/den
            hit=1-C(N-5-(m-y),k)/C(N-5,k)
            pnew+=w*hit
            if y==0:pfresh+=w*hit
    return pnew,pfresh

def main(n):
    rows=[];source=read('round1_results.csv'); routes=read('route_cases.csv')
    for g in range(4):
        m=current(40,g);e=exact(m,m);s=sim(m,m,n,np.random.default_rng(2026112800+g))
        ref=next(r for r in source if r['group']=='current_counterfactual' and r['scenario']==f'40cards_G{g}')
        assert abs(e[2]-float(ref['open_exact']))<1e-12
        assert abs(s[2]-e[2])<=5*math.sqrt(e[2]*(1-e[2])/n)+1e-12
        rows.append(dict(copies=g,hold=e[0],blocked=e[1],open=e[2],hold_mc=s[0],blocked_mc=s[1],open_mc=s[2],trials=n,seed=2026112800+g))
    write('opening_rates.csv',rows)
    grid=[];baseline=[]
    # Relative to extended no-G payoff. C: compact cost without G; B: benefit of compact versus extended under G;
    # L: cost of waiting until G reveals itself vs precommitting to compact, K: cost of using counter.
    # Not observed win rates. Relative score units, optionally interpreted as pp with feasible baselines.
    for r in rows:
        for c in (0,1,3,5,10):
            for b in (10,20,40,60):
                for l in (0,5,10,20,40):
                    for k in (0,5,10):
                        for mode,p,q in [('average',r['open'],r['blocked']),('no_counter',r['hold'],0),('guaranteed_counter',0,r['hold'])]:
                            # fixed extended baseline under G is set to -B (compact G score=0) for relative comparison only.
                            # subtract K in every strategy in blocked state; assumes G attempted and answered identically.
                            a=-p*b-q*k;pre=-(1-p)*c-q*k;wait=-p*min(l,b)-q*k
                            best=max(a,pre,wait)
                            d=dict(copies=r['copies'],information=mode,p=p,q=q,C=c,B=b,L=l,K=k,extended=a,precompact=pre,adaptive=wait,pre_minus_extended=pre-a,pre_minus_adaptive=pre-wait,best='|'.join(nm for nm,v in [('extended',a),('precompact',pre),('adaptive',wait)] if abs(v-best)<1e-10))
                            grid.append(d)
                            if (c,b,l,k)==(5,40,10,5) and mode=='average':baseline.append(d)
    write('strategy_grid.csv',grid);write('baseline.csv',baseline)
    dr=[]
    for r in rows:
        for case in routes:
            k=int(case['draws']); p=r['open']; q=r['blocked']
            dr.append(dict(copies=r['copies'],case=case['case'],policy=case['policy'],draws_if_active=k,mean_gross_draws=p*k,mean_net_cards_if_g_always_attempted=p*(k-1)-q,mean_gross_draws_mc=r['open_mc']*k))
    write('route_draws.csv',dr)
    timing=[]
    for case in routes:
        total=int(case['draws'])
        for already in range(total+1):
            timing.append(dict(case=case['case'],policy=case['policy'],total_summon_events=total,events_before_resolution=already,draws_after_resolution=total-already))
    write('timing.csv',timing)
    historical=[]
    for year in range(2023,2027):
        for group,scenario in [('wcs_full_caps',f'{year}_40cards'),('sample_pool',str(year))]:
            r=next(r for r in source if r['group']==group and r['scenario']==scenario)
            p=float(r['open_exact'])
            historical.append(dict(year=year,model=group,p=p,pre_minus_extended=45*p-5,pre_minus_adaptive=15*p-5))
    write('historical_scenarios.csv',historical)
    candidates=[]
    for profile,g,m in [('WCS2025_Ryzeal_Ash_Veiler_Imperm',2,5),('WCS2026_Dracotail_Ash_only',1,3),('hypothetical_8',1,8),('hypothetical_12',1,12)]:
        for k in range(6):
            a,b=getprob(40,g,m,k);candidates.append(dict(profile=profile,g=g,candidates=m,draws=k,at_least_one_candidate=a,none_initial_and_new=b))
    write('candidate_draws.csv',candidates)
    assert all(abs(r['open']+r['blocked']-r['hold'])<1e-12 for r in rows)
    assert all(x['adaptive']>=x['extended']-1e-12 for x in grid)
    assert all(x['adaptive']>=x['precompact']-1e-12 for x in grid if x['L']==0)
    print('hand trials',4*n,'strategy grid',len(grid),'route rows',len(dr),'candidate rows',len(candidates))
    for r,d in zip(rows,baseline):print(r['copies'], 'p',round(r['open']*100,4),'p_mc',round(r['open_mc']*100,4),'q',round(r['blocked']*100,4),'pre-full',round(d['pre_minus_extended'],4),'pre-wait',round(d['pre_minus_adaptive'],4))
    print('checks passed')
    plots(rows,grid,dr)

def plots(rows,grid,dr):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    fig,ax=plt.subplots(figsize=(9,5));x=np.arange(4);p=np.array([r['open'] for r in rows]);q=np.array([r['blocked'] for r in rows]);ax.bar(x,p*100,label='初手通過候補',color='#287a9b');ax.bar(x,q*100,bottom=p*100,label='指定対策札あり',color='#a7b9c9');ax.set(xticks=x,xticklabels=[f'{i}枚' for i in x],ylabel='割合 (%)',title='同じ採用率・対策札条件で増Gの枚数だけを変更');ax.legend();fig.text(.09,.015,'第1回モデルを再利用。40枚・採用独立・仮想規制比較。実戦適用率ではない。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'01_opening_rates.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));ps=np.linspace(0,.4,401);ax.plot(ps*100,45*ps-5,label='事前ケア − 固定拡張（B=40）');ax.plot(ps*100,15*ps-5,label='事前ケア − 発動後対応（L=10）');ax.axhline(0,color='gray',lw=1)
    for i,r in enumerate(rows[1:],1):ax.axvline(r['open']*100,color='gray',ls=':',lw=1);ax.text(r['open']*100+.25,-4.6,f'{i}枚',fontsize=10)
    ax.set(xlabel='初手通過候補率 (%)',ylabel='仮想評価差 (pt)',title='事前ケアの価値は発動後に変更できるかで変わる');ax.legend();fig.text(.08,.015,'C=5, B=40, L=10。勝率の実測・推定ではない。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'02_strategy_thresholds.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));labels=['ライゼオル\n中断','ライゼオル\n短縮','ライゼオル\n拡張','ドラゴンテイル\n持越し','ドラゴンテイル\n1融合','ドラゴンテイル\n2融合'];vals=[r['draws_if_active'] for r in dr if r['copies']==1];bars=ax.bar(labels,vals,color=['#287a9b']*3+['#c48553']*3);ax.bar_label(bars);ax.set(ylabel='相手の増Gによるドロー枚数',title='同一テーマ内の展開例を比較（増Gが最初から適用）',ylim=(0,6));fig.text(.08,.015,'WCS2025/2026の構築を用いた条件付き手順。対戦・勝率の再現ではない。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'03_routes.png');plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--trials',type=int,default=1000000);a=p.parse_args();main(a.trials)
