import csv, itertools as it, math, pathlib, argparse
from functools import lru_cache
import numpy as np
P=pathlib.Path(__file__).resolve().parent
C=math.comb
# profile: main deck size, Maxx C, Ash, Called by, Crossout
@lru_cache(None)
def response(d):
    N,g,a,b,c=d; o=N-g-a-b-c; out=np.zeros(3)
    for x,y,z,w in it.product(*(range(k+1) for k in (g,a,b,c))):
        t=5-x-y-z-w
        if 0<=t<=o:
            p=C(g,x)*C(a,y)*C(b,z)*C(c,w)*C(o,t)/C(N,5)
            out+=p*np.array([y+z>0 or (w>0 and x<g),y+z+w>0,w>0 and x==g])
    return out

def hold(d): return 1-C(d[0]-d[1],5)/C(d[0],5)
def exact(back,front):
    h=sum(w*hold(d) for d,w in back); r=sum((w*response(d) for d,w in front),np.zeros(3))
    return np.array([h,h*r[0],h*(1-r[0]),h*(1-r[1]),h*r[2]])
def sim(back,front,n,rng):
    # Independent random deck identity, followed by sampling WITHOUT replacement.
    h=np.zeros(n,bool); blocked=np.zeros(n,bool)
    def groups(m):
        ids=rng.choice(len(m),n,p=[w for d,w in m]) if len(m)>1 else np.zeros(n,dtype=int)
        for i,(d,w) in enumerate(m):yield d,ids==i
    for (N,g,a,b,c),idx in groups(back):
        if g:h[idx]=rng.hypergeometric(g,N-g,5,int(idx.sum()))>0
    for (N,g,a,b,c),idx in groups(front):
        left=np.full(int(idx.sum()),5,dtype=np.int16); total=N; draws=[]
        for k in (g,a,b,c):
            x=rng.hypergeometric(k,total-k,left) if k else np.zeros(len(left),np.int16)
            draws.append(x);left-=x;total-=k
        G,A,B,X=draws;blocked[idx]=(A+B>0)|((X>0)&(G<g))
    return np.array([h.sum(),(h&blocked).sum(),(h&~blocked).sum()])/n

def one(d):return [(d,1.)]
def current(N,g=1,ash=3,pg=.983,pa=.948,px=.411):
    return [((N,g*G,ash*A,0,X),p) for G,A,X in it.product((0,1),repeat=3) if (p:=(pg if G else 1-pg)*(pa if A else 1-pa)*(px if X else 1-px))>0]
def write(name,rows):
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main(n):
    profiles=list(csv.DictReader((P/'deck_profiles.csv').open(encoding='utf-8-sig')));rows=[]
    def run(group,label,back,front):
        seed=2026112700+len(rows);e=exact(back,front);s=sim(back,front,n,np.random.default_rng(seed));r=dict(group=group,scenario=label,trials=n,seed=seed)
        for k,i,j in zip(('hold','blocked','open'),e,s):r.update({k+'_exact':i,k+'_mc':j})
        r.update(naive_open_exact=e[3],crossout_no_target_joint_exact=e[4],open_error_pp=100*(s[2]-e[2]),open_mc_se_pp=100*math.sqrt(e[2]*(1-e[2])/n));rows.append(r)
    for N in (40,45,50,60):
        for g in range(4):
            m=current(N,g);run('current_counterfactual',f'{N}cards_G{g}',m,m)
        for y,g,b in [(2023,3,2),(2024,3,2),(2025,2,2),(2026,1,1)]:
            d=one((N,g,3,b,1));run('wcs_full_caps',f'{y}_{N}cards',d,d)
    for a in (1,2,3):
        m=current(40,ash=a);run('ash_copies',f'Ash{a}',m,m)
    for x in (0,.411,1):
        m=current(40,px=x);run('crossout_adoption',f'Crossout{x}',m,m)
    for a,b,c in [(0,0,0),(3,0,0),(3,0,1),(3,1,1),(3,2,1)]:
        run('counter_sensitivity',f'A{a}_B{b}_X{c}',one((40,1,3,0,0)),one((40,1,a,b,c)))
    for y in ('2023','2024','2025','2026'):
        ps=[r for r in profiles if r['year']==y];ds=[tuple(int(r[k]) for k in ('size','g','ash','called','crossout')) for r in ps]
        for r,d in zip(ps,ds):run('real_profile_mirror',r['id'],one(d),one(d))
        m=[(d,1/len(ds)) for d in ds];run('sample_pool',y,m,m)
    assert exact(one((40,0,0,0,0)),one((40,0,3,0,1)))[2]==0
    assert abs(response((40,0,0,0,1))[0])<1e-12
    assert abs(response((40,1,0,0,1))[0]-5/40*35/39)<1e-12
    assert all(abs(r['open_error_pp'])<=5*r['open_mc_se_pp']+1e-9 for r in rows)
    write('results.csv',rows)
    obs=[dict(year=y,g_cap=g,applied=k,duels=t,rate=k/t,status='reported' if y==2026 else 'reconstructed') for y,g,k,t in [(2023,3,35,120),(2024,3,68,270),(2025,2,43,264),(2026,1,24,274)]];write('wcs_observed.csv',obs)
    overlaps=[]
    for copies in (1,2,3):
        for g in (0,1):
            pr=np.zeros(4)
            for G,F,U in it.product((0,1),repeat=3):
                p=(.983 if G else .017)*(.717 if F else .283)*(.302 if U else .698);gc,fc,uc=g*G,copies*F,copies*U;o=40-gc-fc-uc
                for x,y,z in it.product(range(gc+1),range(fc+1),range(uc+1)):
                    t=5-x-y-z
                    if 0<=t<=o:pr[2*int(x>0)+int(y+z>0)]+=p*C(gc,x)*C(fc,y)*C(uc,z)*C(o,t)/C(40,5)
            overlaps.append(dict(g_copies=g,charmy_copies_if_adopted=copies,neither=pr[0],charmy_only=pr[1],g_only=pr[2],both=pr[3],any_drawtrap=1-pr[0]))
    write('drawtrap_overlap_exact.csv',overlaps)
    print('conditions',len(rows),'trials',len(rows)*n,'max abs error pp',max(abs(r['open_error_pp']) for r in rows))
    for r in rows:
        if r['group'] in ('sample_pool','ash_copies','counter_sensitivity','real_profile_mirror','crossout_adoption') or (r['group'] in ('current_counterfactual','wcs_full_caps') and '40cards' in r['scenario']):print(r['group'],r['scenario'],*[round(100*r[k+'_exact'],4) for k in ('hold','blocked','open')],round(100*r['open_mc'],4))
    plots(rows,obs)

def plots(rows,obs):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
    def get(gr,s):return next(r for r in rows if r['group']==gr and r['scenario']==s)
    fig,ax=plt.subplots(figsize=(9,5));x=np.arange(4);rs=[get('current_counterfactual',f'40cards_G{g}') for g in x]
    ax.bar(x,[100*r['open_exact'] for r in rs],label='3種の対策札で無効化できない初手',color='#287a9b');ax.bar(x,[100*r['blocked_exact'] for r in rs],bottom=[100*r['open_exact'] for r in rs],label='対策可能な初手',color='#b6c5d1')
    for i,r in enumerate(rs):
        ax.text(i,100*r['hold_exact']+.5,f"{100*r['hold_exact']:.2f}%",ha='center')
        if i:ax.text(i,100*r['open_exact']/2,f"{100*r['open_exact']:.2f}%",ha='center',color='white')
    ax.set(xticks=x,xticklabels=[f'{g}枚' for g in x],ylabel='全試合に対する割合（%）',title='増Gの採用枚数と初手の通過候補率');ax.set_ylim(0,40);ax.legend(loc='upper left',fontsize=10);fig.text(.1,.015,'40枚・両者の構築を独立抽選。2026/11採用率固定の仮想比較（実戦適用率ではない）。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'01_copies.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5));ys=[o['year'] for o in obs];x=np.arange(4);cap=[get('wcs_full_caps',f'{y}_40cards') for y in ys];pool=[get('sample_pool',str(y)) for y in ys]
    for offset,vals,label,color in [(-.26,[100*r['open_exact'] for r in cap],'40枚・規制上限モデル','#8da5b8'),(0,[100*r['open_exact'] for r in pool],'優勝チームの一部レシピ（等重み）','#287a9b'),(.26,[100*o['rate'] for o in obs],'大会全ターンの適用試合率','#cf8751')]:
        bars=ax.bar(x+offset,vals,.25,label=label,color=color);ax.bar_label(bars,fmt='%.1f',fontsize=9,padding=2)
    ax.set(xticks=x,xticklabels=[f"{o['year']}年 ({o['g_cap']}枚)" for o in obs],ylabel='割合（%）',title='WCS：初手モデルと大会観測値（定義が異なる）');ax.set_ylim(0,43);ax.legend(fontsize=9);fig.text(.1,.015,'モデルは第1ターンの初手条件のみ。観測値は全ターン（2023–25は復元値）。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'02_wcs.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,5))
    for g in (1,2,3):
        ds=[40,45,50,60];ax.plot(ds,[100*get('current_counterfactual',f'{D}cards_G{g}')['open_exact'] for D in ds],marker='o',label=f'増G {g}枚')
    ax.set(xticks=ds,ylabel='初手の通過候補率（%）',xlabel='両者のデッキ枚数',title='デッキ枚数による初手の通過候補率の変化');ax.legend();fig.text(.1,.015,'採用率・対策札の採用枚数を固定。デッキサイズの実分布を示すものではない。',fontsize=9);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(P/'03_deck_size.png');plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--trials',type=int,default=1000000);main(p.parse_args().trials)
