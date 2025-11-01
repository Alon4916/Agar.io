"""
Mini Agar.io (Pygame)
---------------------------------
Características:
- Mundo más grande que la pantalla
- Cámara centrada (lerp suave)
- Movimiento hacia el cursor (mouse)
- Crecimiento por masa (radio ~ sqrt(masa))
- Velocidad disminuye con tamaño
- Dash (ESPACIO): impulso hacia el cursor, pierde 5% masa
- Split (Q): divide en dos
- Expulsar masa (E): crea comida
- Bots con IA mejorada: cazan y huyen inteligentemente
- Win: eliminar todos los bots
- Game over: ser comido por un bot más grande
"""
import pygame, sys, random, math, time

# ---------- CONFIG ----------
SCREEN_W, SCREEN_H = 960, 640
WORLD_W, WORLD_H = 3000, 2000
FPS = 60

PLAYER_START_MASS = 1000.0
FOOD_COUNT = 600
BOT_COUNT = 12

# ---------- TUNING ----------
DASH_MASS_COST_RATIO = 0.05
DASH_SPEED_BOOST = 700.0
DASH_DURATION = 0.2
EXPULSION_MASS = 20.0
SPLIT_MASS_MIN = 40.0
SPLIT_COOLDOWN = 6.0  # un poco más largo

# ---------- UTILS ----------
def mass_to_radius(m): return max(6, int(math.sqrt(m)))
def clamp(v,a,b): return max(a, min(b, v))
def lerp(a,b,t): return a+(b-a)*t
def vec_len(x,y): return math.hypot(x,y)

# ---------- ENTITY ----------
class Entity:
    def __init__(self,x,y,mass,color):
        self.x, self.y, self.mass = x, y, mass
        self.color = color
        self.vx = self.vy = 0.0
    @property
    def r(self): return mass_to_radius(self.mass)
    def distance_to(self,o): return vec_len(self.x-o.x, self.y-o.y)

class Player(Entity):
    def __init__(self,x,y,mass):
        super().__init__(x,y,mass,(80,200,80))
        self.dash_timer, self.dash_vx, self.dash_vy = 0,0,0
        self.split_cd = 0
    def base_speed(self): return 220.0 * (self.mass ** -0.25)
    def update(self,dt,tx,ty):
        if self.dash_timer>0:
            self.dash_timer-=dt; self.vx,self.vy=self.dash_vx,self.dash_vy
        else:
            dx,dy=tx-self.x,ty-self.y
            d=vec_len(dx,dy)
            if d>1:
                nx,ny=dx/d,dy/d
                s=self.base_speed()
                self.vx,self.vy=nx*s,ny*s
            else: self.vx=self.vy=0
        self.x+=self.vx*dt; self.y+=self.vy*dt
        self.x=clamp(self.x,0,WORLD_W); self.y=clamp(self.y,0,WORLD_H)
        if self.split_cd>0:self.split_cd-=dt
    def dash(self,tx,ty):
        if self.mass<=5:return
        cost=self.mass*DASH_MASS_COST_RATIO
        self.mass=max(1,self.mass-cost)
        dx,dy=tx-self.x,ty-self.y
        d=vec_len(dx,dy)or 1
        nx,ny=dx/d,dy/d
        self.dash_vx,self.dash_vy=nx*DASH_SPEED_BOOST,ny*DASH_SPEED_BOOST
        self.dash_timer=DASH_DURATION
    def expulsar_masa(self):
        if self.mass<=EXPULSION_MASS+10:return None
        self.mass-=EXPULSION_MASS
        nx, ny = (1,0) if self.vx==0 and self.vy==0 else (self.vx, self.vy)
        len_v = vec_len(nx, ny) or 1
        nx, ny = nx/len_v, ny/len_v
        return Food(self.x + nx*(self.r+10), self.y + ny*(self.r+10), EXPULSION_MASS, (255,220,70))
    def can_split(self): return self.mass>=SPLIT_MASS_MIN*2 and self.split_cd<=0
    def split(self,tx,ty):
        if not self.can_split(): return None
        m = self.mass / 2
        self.mass = m
        dx, dy = tx - self.x, ty - self.y
        d = vec_len(dx, dy) or 1
        nx, ny = dx/d, dy/d
        offset = self.r + mass_to_radius(m) + 150  # más lejos
        c = Player(self.x + nx*offset,
                   self.y + ny*offset,
                   m)
        c.vx, c.vy = nx*350, ny*350  # impulso inicial
        self.split_cd = SPLIT_COOLDOWN
        return c

class Food(Entity):
    def __init__(self,x,y,m=10.0,color=(255,200,50)): super().__init__(x,y,m,color)

class Bot(Entity):
    def __init__(self,x,y,m):
        color=(random.randint(100,255),random.randint(80,255),random.randint(80,255))
        super().__init__(x,y,m,color)
        self.dir_timer=0
    def base_speed(self): return 200.0*(self.mass**-0.25)
    def update(self,dt,world,player):
        closest,threat=None,None
        cd,td=1e9,1e9
        for e in world:
            if e is self:continue
            d=self.distance_to(e)
            if hasattr(e,"mass"):
                if e.mass<self.mass*0.9 and d<cd:closest,cd=e,d
                if e.mass>self.mass*1.1 and d<td:threat,td=e,d
        if threat and td<350:
            dx,dy=self.x-threat.x,self.y-threat.y
            dist=vec_len(dx,dy)or 1
            nx,ny=dx/dist,dy/dist
            sp=self.base_speed()*1.2
            self.vx,self.vy=nx*sp,ny*sp
        elif closest and cd<600:
            dx,dy=closest.x-self.x,closest.y-self.y
            dist=vec_len(dx,dy)or 1
            nx,ny=dx/dist,dy/dist
            sp=self.base_speed()
            self.vx,self.vy=nx*sp,ny*sp
        else:
            self.dir_timer-=dt
            if self.dir_timer<=0:
                ang=random.random()*math.tau
                sp=self.base_speed()*0.7
                self.vx,self.vy=math.cos(ang)*sp,math.sin(ang)*sp
                self.dir_timer=random.uniform(1,3)
        self.x+=self.vx*dt; self.y+=self.vy*dt
        self.x=clamp(self.x,0,WORLD_W); self.y=clamp(self.y,0,WORLD_H)

# ---------- GAME ----------
class Game:
    def __init__(self):
        pygame.init()
        self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
        pygame.display.set_caption("Mini Agar.io Mejorado")
        self.clock=pygame.time.Clock()
        self.font=pygame.font.SysFont(None,26)
        self.bigfont=pygame.font.SysFont(None,64)
        self.state="menu"
        self.reset()

    def reset(self):
        px,py=WORLD_W/2,WORLD_H/2
        self.player=Player(px,py,PLAYER_START_MASS)
        self.cells=[]; self.foods=[]; self.bots=[]
        for _ in range(FOOD_COUNT):
            self.foods.append(Food(random.uniform(0,WORLD_W),random.uniform(0,WORLD_H)))
        for _ in range(BOT_COUNT):
            self.bots.append(Bot(random.uniform(0,WORLD_W),random.uniform(0,WORLD_H),random.uniform(300,1200)))
        self.cam_x,self.cam_y=px,py
        self.game_over,self.win=False,False
        self.death_timer=0

    def world_to_screen(self,wx,wy): 
        return int(wx-self.cam_x+SCREEN_W/2),int(wy-self.cam_y+SCREEN_H/2)

    def center_cam(self,dt):
        t=clamp(5*dt,0,1)
        self.cam_x=lerp(self.cam_x,self.player.x,t)
        self.cam_y=lerp(self.cam_y,self.player.y,t)

    def handle_collisions(self):
        # Jugador y células hijas
        for f in self.foods[:]:
            for e in [self.player]+self.cells:
                if e.distance_to(f)<(e.r+f.r):
                    e.mass+=f.mass; self.foods.remove(f)
                    break
        # Bots vs jugador y células hijas
        for b in self.bots[:]:
            for e in [self.player]+self.cells:
                if e.distance_to(b)<(e.r+b.r):
                    if e.mass>b.mass*1.1:
                        e.mass+=b.mass*0.9; self.bots.remove(b)
                    elif b.mass>e.mass*1.1:
                        if e is self.player:
                            self.game_over=True
                        else:
                            # Bot se come célula hija
                            b.mass += e.mass * 0.9
                            try: self.cells.remove(e)
                            except: pass
        # Bots vs comida
        for b in self.bots:
            for f in self.foods[:]:
                if b.distance_to(f)<(b.r+f.r):
                    b.mass+=f.mass; self.foods.remove(f)
        # Bots entre sí
        for b in self.bots[:]:
            for o in self.bots[:]:
                if b is o: continue
                if b.distance_to(o)<(b.r+o.r) and b.mass>o.mass*1.1:
                    b.mass+=0.8*o.mass
                    try:self.bots.remove(o)
                    except:pass

    def replenish_food(self):
        while len(self.foods)<FOOD_COUNT:
            self.foods.append(Food(random.uniform(0,WORLD_W),random.uniform(0,WORLD_H)))

    def draw(self):
        self.screen.fill((25,25,40))
        for f in self.foods:
            sx,sy=self.world_to_screen(f.x,f.y)
            pygame.draw.circle(self.screen,f.color,(sx,sy),f.r)
        for b in self.bots:
            sx,sy=self.world_to_screen(b.x,b.y)
            pygame.draw.circle(self.screen,b.color,(sx,sy),b.r)
        sx,sy=self.world_to_screen(self.player.x,self.player.y)
        pygame.draw.circle(self.screen,self.player.color,(sx,sy),self.player.r)
        pygame.draw.circle(self.screen,(0,0,0),(sx,sy),self.player.r,2)
        for c in self.cells:
            sx,sy=self.world_to_screen(c.x,c.y)
            pygame.draw.circle(self.screen,c.color,(sx,sy),c.r)
            pygame.draw.circle(self.screen,(0,0,0),(sx,sy),2)

        # HUD
        txt=self.font.render(f"Masa: {int(self.player.mass)} | Bots restantes: {len(self.bots)}",True,(230,230,230))
        self.screen.blit(txt,(10,10))

        # Tabla de masas
        scores = sorted([(int(b.mass), b.color) for b in self.bots], reverse=True)
        self.screen.blit(self.font.render("Masa de bots:",True,(255,255,200)),(SCREEN_W-180,10))
        for i,(m,color) in enumerate(scores[:8]):
            pygame.draw.circle(self.screen,color,(SCREEN_W-160,40+i*20),6)
            t=self.font.render(str(m),True,(255,255,255))
            self.screen.blit(t,(SCREEN_W-140,33+i*20))

        if self.state=="menu":
            title=self.bigfont.render("Mini Agar.io",True,(80,255,120))
            self.screen.blit(title,(SCREEN_W//2-title.get_width()//2,140))
            lines=[
                "Cómo jugar:",
                "• Mueve el mouse para moverte.",
                "• SPACE: Dash (pierdes 5% de masa)",
                "• Q: Dividirte",
                "• E: Expulsar masa",
                "Come y sobrevive contra los bots.",
                "Presiona cualquier tecla para comenzar..."
            ]
            for i,l in enumerate(lines):
                t=self.font.render(l,True,(230,230,230))
                self.screen.blit(t,(SCREEN_W//2-t.get_width()//2,260+i*28))

        if self.game_over:
            alpha=int(255*min(1,self.death_timer/1.5))
            surf=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
            pygame.draw.circle(surf,(255,40,40,alpha),(SCREEN_W//2,SCREEN_H//2),min(SCREEN_W,SCREEN_H)//2)
            self.screen.blit(surf,(0,0))
            msg=self.bigfont.render("GAME OVER",True,(255,80,80))
            self.screen.blit(msg,(SCREEN_W//2-msg.get_width()//2,SCREEN_H//2-40))
        if self.win:
            w=self.bigfont.render("¡GANASTE!",True,(50,255,80))
            self.screen.blit(w,(SCREEN_W//2-w.get_width()//2,SCREEN_H//2-40))
        pygame.display.flip()

    def run(self):
        while True:
            dt=self.clock.tick(FPS)/1000
            for e in pygame.event.get():
                if e.type==pygame.QUIT:pygame.quit();sys.exit()
                if e.type==pygame.KEYDOWN:
                    if self.state=="menu":self.state="play"
                    if e.key==pygame.K_ESCAPE:pygame.quit();sys.exit()
                    if self.state=="play" and not self.game_over:
                        mx,my=pygame.mouse.get_pos()
                        wx,wy=self.cam_x-SCREEN_W/2+mx,self.cam_y-SCREEN_H/2+my
                        if e.key==pygame.K_SPACE:self.player.dash(wx,wy)
                        if e.key==pygame.K_e:
                            nf=self.player.expulsar_masa()
                            if nf:self.foods.append(nf)
                        if e.key==pygame.K_q:
                            child=self.player.split(wx,wy)
                            if child:self.cells.append(child)

            if self.state=="play" and not self.game_over and not self.win:
                mx,my=pygame.mouse.get_pos()
                wx,wy=self.cam_x-SCREEN_W/2+mx,self.cam_y-SCREEN_H/2+my
                self.player.update(dt,wx,wy)
                for c in self.cells:
                    c.update(dt,wx,wy)
                for b in self.bots:b.update(dt,self.foods+self.bots+[self.player]+self.cells,self.player)
                self.handle_collisions()
                self.replenish_food()
                if len(self.bots)==0:self.win=True
            elif self.game_over:
                self.death_timer+=dt

            self.center_cam(dt)
            self.draw()

if __name__=="__main__":
    Game().run()