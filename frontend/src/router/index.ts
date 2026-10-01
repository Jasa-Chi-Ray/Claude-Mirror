import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

function hasClaudeSession(): boolean {
  return false
}

function clearAccessibleCookies(): void {
  const cookies = document.cookie.split(';')
  for (const entry of cookies) {
    const [rawName] = entry.split('=', 1)
    const name = rawName?.trim()
    if (!name) continue
    document.cookie = `${name}=; Path=/; Max-Age=0`
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/login/index.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/pages/login/index.vue')
  },
  {
    path: '/login-claude',
    alias: '/login-chatgpt',
    name: 'LoginClaude',
    component: () => import('@/pages/login/claude.vue')
  },
  {
    path: '/account',
    name: 'Account',
    component: () => import('@/layouts/index.vue'),
    redirect: '/account/overview',
    children: [
      {
        path: 'overview',
        name: 'Overview',
        component: () => import('@/pages/account/overview.vue'),
        meta: { title: '运维概览', requiresAdmin: true }
      },
      {
        path: 'user',
        name: 'User',
        component: () => import('@/pages/account/user.vue'),
        meta: { title: '用户', requiresAdmin: true }
      },
      {
        path: 'claude',
        alias: 'chatgpt',
        name: 'ClaudeAccounts',
        component: () => import('@/pages/account/claude.vue'),
        meta: { title: 'Claude 账号', requiresAdmin: true }
      },
      {
        path: 'pools',
        alias: 'gptcar',
        name: 'AccountPools',
        component: () => import('@/pages/account/pools.vue'),
        meta: { title: '账号池', requiresAdmin: true }
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/pages/account/logs.vue'),
        meta: { title: '日志', requiresAdmin: true }
      },
      {
        path: 'announcements',
        name: 'Announcements',
        component: () => import('@/pages/account/announcement.vue'),
        meta: { title: '公告', requiresAdmin: true }
      },
      {
        path: 'proxy',
        name: 'Proxy',
        component: () => import('@/pages/account/proxy.vue'),
        meta: { title: '代理', requiresAdmin: true }
      },
      {
        path: 'scripts',
        name: 'Scripts',
        component: () => import('@/pages/account/scripts.vue'),
        meta: { title: '脚本', requiresAdmin: true }
      },
      {
        path: 'access',
        name: 'AccessControl',
        component: () => import('@/pages/account/access.vue'),
        meta: { title: '访问与安全', requiresAdmin: true }
      },
      {
        path: 'political-moderation',
        name: 'PoliticalModeration',
        component: () => import('@/pages/account/political-moderation.vue'),
        meta: { title: '政治敏感内容屏蔽', requiresAdmin: true }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/pages/account/profile.vue'),
        meta: { title: '账户中心' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory('/admin/'),
  routes
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()
  const isLoginPage = ['/login', '/login-claude', '/login-chatgpt'].includes(to.path)

  if (isLoginPage && hasClaudeSession()) {
    window.location.replace('/chat')
    next(false)
    return
  }

  const authenticated = await userStore.hydrate()
  if (authenticated && userStore.isAdmin && to.name === 'Profile') {
    next('/account/overview')
    return
  }

  if (to.meta.requiresAdmin && (!authenticated || !userStore.isAdmin)) {
    clearAccessibleCookies()
    window.location.replace('/admin#/')
    next(false)
    return
  }
  
  if (to.path !== '/login' && to.path !== '/register' && !authenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router
