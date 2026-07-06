import React, { useState, useEffect, useRef } from 'react';
import { 
  CheckSquare, Trash2, Calendar as CalendarIcon, 
  Target, Award, Bell, Settings as SettingsIcon, MessageSquare, 
  Plus, AlertTriangle, ArrowRight, Zap, CheckCircle2, Clock, User,
  ListTodo, RefreshCw, BarChart2, Edit
} from 'lucide-react';
import './App.css';

const API_BASE = 'http://127.0.0.1:8000/api';

export default function App() {
  const now = new Date();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [tasks, setTasks] = useState([]);
  const [goals, setGoals] = useState([]);
  const [habits, setHabits] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [memories, setMemories] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [preferences, setPreferences] = useState({});
  const [categories, setCategories] = useState([]);   // <-- dynamic categories
  const [scheduleOverview, setScheduleOverview] = useState({ schedule: {}, summary: {} });
  const [review, setReview] = useState({ summary: {} });
  const [coachReport, setCoachReport] = useState({ personalized_recommendations: [], productivity_score: 0 });
  const [calendarCursor, setCalendarCursor] = useState(new Date(now.getFullYear(), now.getMonth(), 1));
  const [selectedTaskCategory, setSelectedTaskCategory] = useState('All');
  const [taskStatusFilter, setTaskStatusFilter] = useState('pending');
  const [chatHistory, setChatHistory] = useState([
    { role: 'assistant', text: "Hello! I am Nova, your personal productivity assistant. How can I help you conquer your goals today?" }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  // Modals state
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showGoalModal, setShowGoalModal] = useState(false);
  const [showHabitModal, setShowHabitModal] = useState(false);
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  // Form states
  const [taskForm, setTaskForm] = useState({
    title: '', description: '', category: '', priority: 'medium',
    due_date: '', scheduled_time: '', duration: 30, goal_id: '', reminder_time: '',
    newCategoryName: ''  // inline new-category field
  });
  const [goalForm, setGoalForm] = useState({
    title: '', description: '', category: '', target_date: '',
    newCategoryName: ''
  });
  const [habitForm, setHabitForm] = useState({
    title: '', description: '', category: '', frequency: 'daily',
    target_count: 1, start_date: '', reminder_time: '', goal_id: '',
    newCategoryName: ''
  });
  const [memoryForm, setMemoryForm] = useState({
    content: '', memory_type: 'context', tags: ''
  });

  const [editingTaskId, setEditingTaskId] = useState(null);

  // Category manager state (used inside renderTasks via closure)
  const catMgrState = useState('');
  const renamingState = useState(null);
  const renameValState = useState('');

  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isTyping]);

  const fetchData = async () => {
    try {
      const ts = Date.now();
      // Fetch tasks
      const tasksRes = await fetch(`${API_BASE}/tasks?t=${ts}`);
      const tasksData = await tasksRes.json();
      if (tasksData.status === 'success') setTasks(tasksData.tasks);

      // Fetch categories
      try {
        const catsRes = await fetch(`${API_BASE}/categories?t=${ts}`);
        const catsData = await catsRes.json();
        if (catsData.status === 'success') setCategories(catsData.categories);
      } catch (_) { /* non-critical */ }

      // Fetch goals
      const goalsRes = await fetch(`${API_BASE}/goals?t=${ts}`);
      const goalsData = await goalsRes.json();
      if (goalsData.status === 'success') setGoals(goalsData.goals);

      const habitsRes = await fetch(`${API_BASE}/habits?t=${ts}`);
      const habitsData = await habitsRes.json();
      if (habitsData.status === 'success') setHabits(habitsData.habits);

      const remindersRes = await fetch(`${API_BASE}/reminders?t=${ts}`);
      const remindersData = await remindersRes.json();
      if (remindersData.status === 'success') setReminders(remindersData.reminders);

      // Fetch conflicts
      const conflictsRes = await fetch(`${API_BASE}/conflicts?t=${ts}`);
      const conflictsData = await conflictsRes.json();
      if (conflictsData.status === 'success') setConflicts(conflictsData.conflicts);

      // Fetch recommendations
      const recsRes = await fetch(`${API_BASE}/recommendations?t=${ts}`);
      const recsData = await recsRes.json();
      if (recsData.status === 'success') setRecommendations(recsData.recommendations);

      const scheduleRes = await fetch(`${API_BASE}/schedule?horizon=day&t=${ts}`);
      const scheduleData = await scheduleRes.json();
      if (scheduleData.status === 'success') setScheduleOverview(scheduleData);

      const reviewRes = await fetch(`${API_BASE}/review?period=week&t=${ts}`);
      const reviewData = await reviewRes.json();
      if (reviewData.status === 'success') setReview(reviewData);

      const coachRes = await fetch(`${API_BASE}/coach?period=day&t=${ts}`);
      const coachData = await coachRes.json();
      if (coachData.status === 'success') setCoachReport(coachData);

      // Notifications: fire-and-forget the process trigger so a 403 never aborts the rest
      try {
        await fetch(`${API_BASE}/notifications/process?t=${ts}`, { method: 'POST' });
      } catch (_) { /* ignore — non-critical background trigger */ }
      try {
        const notificationsRes = await fetch(`${API_BASE}/notifications?limit=10&t=${ts}`);
        const notificationsData = await notificationsRes.json();
        if (notificationsData.status === 'success') setNotifications(notificationsData.notifications);
      } catch (_) { /* ignore */ }

      try {
        const memoriesRes = await fetch(`${API_BASE}/memory?limit=6&t=${ts}`);
        const memoriesData = await memoriesRes.json();
        if (memoriesData.status === 'success') setMemories(memoriesData.memories);
      } catch (_) { /* ignore */ }

      // Fetch preferences
      try {
        const prefsRes = await fetch(`${API_BASE}/preferences?t=${ts}`);
        const prefsData = await prefsRes.json();
        if (prefsData.status === 'success') setPreferences(prefsData.preferences);
      } catch (_) { /* ignore */ }

    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    }
  };

  // --- Task Operations ---
  
  const handleNewTaskClick = () => {
    setEditingTaskId(null);
    setTaskForm({
      title: '', description: '', category: '', priority: 'medium',
      due_date: '', scheduled_time: '', duration: 30, goal_id: '', reminder_time: '',
      status: 'pending',
      newCategoryName: ''
    });
    setShowTaskModal(true);
  };

  const formatDateTimeLocal = (dateStr) => {
    if (!dateStr) return '';
    const iso = dateStr.replace(' ', 'T');
    return iso.substring(0, 16);
  };

  const handleEditTask = async (task) => {
    setEditingTaskId(task.id);
    let reminderTime = '';
    try {
      const res = await fetch(`${API_BASE}/reminders?task_id=${task.id}`);
      const data = await res.json();
      if (data.status === 'success' && data.reminders && data.reminders.length > 0) {
        const pending = data.reminders.find(r => r.is_sent === 0);
        if (pending && pending.reminder_time) {
          reminderTime = pending.reminder_time;
        }
      }
    } catch (err) {
      console.error('Error fetching reminder:', err);
    }

    setTaskForm({
      title: task.title || '',
      description: task.description || '',
      category: task.category || '',
      priority: task.priority || 'medium',
      due_date: task.due_date ? task.due_date.substring(0, 10) : '',
      scheduled_time: formatDateTimeLocal(task.scheduled_time),
      duration: task.duration || 30,
      goal_id: task.goal_id || '',
      reminder_time: formatDateTimeLocal(reminderTime),
      status: task.status || 'pending',
      newCategoryName: ''
    });
    setShowTaskModal(true);
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    try {
      // Resolve category: auto-create if user typed a new name
      let resolvedCategory = taskForm.category;
      if (taskForm.category === '__new__') {
        const newName = taskForm.newCategoryName.trim();
        if (!newName) { alert('Please enter a category name.'); return; }
        const catRes = await fetch(`${API_BASE}/categories`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName })
        });
        const catData = await catRes.json();
        resolvedCategory = catData.category?.name || newName;
      }

      const payload = {
        title: taskForm.title,
        description: taskForm.description || null,
        category: resolvedCategory || 'General',
        priority: taskForm.priority,
        due_date: taskForm.due_date || null,
        scheduled_time: taskForm.scheduled_time || null,
        duration: taskForm.duration ? parseInt(taskForm.duration) : null,
        goal_id: taskForm.goal_id ? parseInt(taskForm.goal_id) : null,
      };

      const res = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'success' || data.status === 'warning') {
        if (taskForm.reminder_time && data.task?.id) {
          await fetch(`${API_BASE}/reminders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              task_id: data.task.id,
              reminder_time: taskForm.reminder_time,
              message: `Reminder: ${taskForm.title}`
            })
          });
        }
        setShowTaskModal(false);
        setTaskForm({
          title: '', description: '', category: '', priority: 'medium',
          due_date: '', scheduled_time: '', duration: 30, goal_id: '', reminder_time: '',
          status: 'pending',
          newCategoryName: ''
        });
        fetchData();
      }
    } catch (err) {
      alert('Error creating task: ' + err.message);
    }
  };

  const handleUpdateTask = async (e, forceConfirmation = false) => {
    if (e) e.preventDefault();
    try {
      let resolvedCategory = taskForm.category;
      if (taskForm.category === '__new__') {
        const newName = taskForm.newCategoryName.trim();
        if (!newName) { alert('Please enter a category name.'); return; }
        const catRes = await fetch(`${API_BASE}/categories`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName })
        });
        const catData = await catRes.json();
        resolvedCategory = catData.category?.name || newName;
      }

      const payload = {
        title: taskForm.title,
        description: taskForm.description || null,
        category: resolvedCategory || 'General',
        priority: taskForm.priority,
        due_date: taskForm.due_date || null,
        scheduled_time: taskForm.scheduled_time || null,
        duration: taskForm.duration ? parseInt(taskForm.duration) : null,
        goal_id: taskForm.goal_id ? parseInt(taskForm.goal_id) : null,
        reminder_time: taskForm.reminder_time || null,
        status: taskForm.status || 'pending',
        confirmation: forceConfirmation
      };

      const res = await fetch(`${API_BASE}/tasks/${editingTaskId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'confirmation_required') {
        triggerConfirmModal(
          data.message,
          async () => {
            await handleUpdateTask(null, true);
          }
        );
        return;
      }
      if (data.status === 'success') {
        setShowTaskModal(false);
        setEditingTaskId(null);
        setTaskForm({
          title: '', description: '', category: '', priority: 'medium',
          due_date: '', scheduled_time: '', duration: 30, goal_id: '', reminder_time: '',
          status: 'pending',
          newCategoryName: ''
        });
        fetchData();
      } else {
        alert(data.message || 'Error updating task.');
      }
    } catch (err) {
      alert('Error updating task: ' + err.message);
    }
  };

  const handleTaskFormSubmit = async (e) => {
    e.preventDefault();
    if (editingTaskId) {
      await handleUpdateTask(e);
    } else {
      await handleCreateTask(e);
    }
  };

  const toggleTaskStatus = async (task) => {
    const isCompleted = task.status === 'completed';
    const newStatus = isCompleted ? 'pending' : 'completed';

    // Safety constraint: Never modify completed tasks without confirmation
    if (isCompleted) {
      triggerConfirmModal(
        `Are you sure you want to mark '${task.title}' as incomplete?`,
        async () => {
          await updateTaskStatusApi(task.id, newStatus, true);
        }
      );
    } else {
      await updateTaskStatusApi(task.id, newStatus, false);
    }
  };

  const updateTaskStatusApi = async (id, status, confirmation) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, confirmation })
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchData();
      }
    } catch (err) {
      console.error('Error updating task status:', err);
    }
  };

  const handleDeleteTask = (task) => {
    // Safety constraint: Never delete tasks without confirmation
    triggerConfirmModal(
      `Are you sure you want to delete the task '${task.title}'? This action cannot be undone.`,
      async () => {
        try {
          const res = await fetch(`${API_BASE}/tasks/${task.id}?confirmation=true`, {
            method: 'DELETE'
          });
          const data = await res.json();
          if (data.status === 'success') {
            fetchData();
          }
        } catch (err) {
          console.error('Error deleting task:', err);
        }
      }
    );
  };

  // --- Goal Operations ---

  const handleCreateGoal = async (e) => {
    e.preventDefault();
    try {
      let resolvedCategory = goalForm.category;
      if (goalForm.category === '__new__') {
        const newName = goalForm.newCategoryName.trim();
        if (!newName) { alert('Please enter a category name.'); return; }
        const catRes = await fetch(`${API_BASE}/categories`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName })
        });
        const catData = await catRes.json();
        resolvedCategory = catData.category?.name || newName;
      }

      const payload = {
        title: goalForm.title,
        description: goalForm.description || null,
        category: resolvedCategory || null,
        target_date: goalForm.target_date || null
      };

      const res = await fetch(`${API_BASE}/goals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'success') {
        setShowGoalModal(false);
        setGoalForm({ title: '', description: '', category: '', target_date: '', newCategoryName: '' });
        fetchData();
      }
    } catch (err) {
      alert('Error creating goal: ' + err.message);
    }
  };

  const handleCreateHabit = async (e) => {
    e.preventDefault();
    try {
      let resolvedCategory = habitForm.category;
      if (habitForm.category === '__new__') {
        const newName = habitForm.newCategoryName.trim();
        if (!newName) { alert('Please enter a category name.'); return; }
        const catRes = await fetch(`${API_BASE}/categories`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName })
        });
        const catData = await catRes.json();
        resolvedCategory = catData.category?.name || newName;
      }

      const payload = {
        title: habitForm.title,
        description: habitForm.description || null,
        category: resolvedCategory || 'General',
        frequency: habitForm.frequency,
        target_count: parseInt(habitForm.target_count || 1),
        goal_id: habitForm.goal_id ? parseInt(habitForm.goal_id) : null,
        start_date: habitForm.start_date || null,
        reminder_time: habitForm.reminder_time || null
      };
      const res = await fetch(`${API_BASE}/habits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'success') {
        setShowHabitModal(false);
        setHabitForm({
          title: '', description: '', category: '', frequency: 'daily',
          target_count: 1, start_date: '', reminder_time: '', goal_id: '', newCategoryName: ''
        });
        fetchData();
      }
    } catch (err) {
      alert('Error creating habit: ' + err.message);
    }
  };

  const handleHabitCheckIn = async (habit) => {
    try {
      const res = await fetch(`${API_BASE}/habits/${habit.id}/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed_count: 1 })
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchData();
      }
    } catch (err) {
      console.error('Error logging habit:', err);
    }
  };

  const handleCreateMemory = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...memoryForm,
          tags: memoryForm.tags ? memoryForm.tags.split(',').map(tag => tag.trim()).filter(Boolean) : []
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setShowMemoryModal(false);
        setMemoryForm({ content: '', memory_type: 'context', tags: '' });
        fetchData();
      }
    } catch (err) {
      alert('Error saving memory: ' + err.message);
    }
  };

  // --- Safety Confirmation Modal Helper ---
  
  const triggerConfirmModal = (message, onConfirm) => {
    setConfirmAction({ message, onConfirm });
    setShowConfirmModal(true);
  };

  const executeConfirmAction = async () => {
    if (confirmAction && confirmAction.onConfirm) {
      await confirmAction.onConfirm();
    }
    setShowConfirmModal(false);
    setConfirmAction(null);
  };

  // --- Chat Assistant Client (with Streaming Support) ---

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput;
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', text: userText }]);
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText })
      });

      if (!response.body) {
        throw new Error('ReadableStream not supported.');
      }

      setChatHistory(prev => [...prev, { role: 'assistant', text: '' }]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          buffer += chunk;
          
          const lines = buffer.split('\n');
          // Save the last incomplete line back to buffer
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            if (trimmed.startsWith('data: ')) {
              const dataContent = trimmed.slice(6).trim();
              if (dataContent === '[DONE]') {
                done = true;
                break;
              }
              try {
                const parsed = JSON.parse(dataContent);
                if (parsed.text) {
                  setChatHistory(prev => {
                    const last = prev[prev.length - 1];
                    const rest = prev.slice(0, -1);
                    return [...rest, { role: 'assistant', text: last.text + parsed.text }];
                  });
                }
              } catch {
                // Ignore json parse error for incomplete lines
              }
            }
          }
        }
      }
      
      setIsTyping(false);
      // Refresh dashboard data as tools might have run
      fetchData();
      
    } catch (err) {
      setIsTyping(false);
      setChatHistory(prev => [...prev, { role: 'assistant', text: 'Sorry, I encountered an error communicating with the agent server: ' + err.message }]);
    }
  };

  const handleAlertBannerAction = (bannerActionType) => {
    setActiveTab('chat');
    if (bannerActionType === 'conflict') {
      setChatInput('Nova, I see some scheduling conflicts. Can you help me reorganize my schedule intelligently?');
    } else if (bannerActionType === 'overdue') {
      setChatInput('Nova, what tasks are currently overdue, and what recovery plan do you suggest?');
    }
  };

  // Stats calculation
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter(t => t.status === 'completed').length;
  const pendingTasks = tasks.filter(t => t.status === 'pending').length;
  const successRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
  const todaySchedule = Object.values(scheduleOverview.schedule || {}).flat();
  const unreadNotifications = notifications.filter(n => n.status === 'pending').length;
  const overdueTasksCount = tasks.filter(t => {
    if (t.status === 'pending' && t.due_date) {
      return t.due_date < new Date().toISOString();
    }
    return false;
  }).length;

  return (
    <div className="app-container">
      {/* Side Navigation Bar */}
      <aside className="sidebar">
        <div>
          <div className="brand-section">
            <div className="brand-icon">
              <Zap size={20} color="#fff" />
            </div>
            <span className="brand-name">Nova AI</span>
          </div>

          <nav className="nav-links">
            <div className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
              <ListTodo size={18} />
              <span>Dashboard</span>
            </div>
            <div className={`nav-item ${activeTab === 'calendar' ? 'active' : ''}`} onClick={() => setActiveTab('calendar')}>
              <CalendarIcon size={18} />
              <span>Calendar</span>
            </div>
            <div className={`nav-item ${activeTab === 'tasks' ? 'active' : ''}`} onClick={() => setActiveTab('tasks')}>
              <CheckSquare size={18} />
              <span>Tasks</span>
            </div>
            <div className={`nav-item ${activeTab === 'goals' ? 'active' : ''}`} onClick={() => setActiveTab('goals')}>
              <Target size={18} />
              <span>Goals</span>
            </div>
            <div className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
              <MessageSquare size={18} />
              <span>AI Chat</span>
            </div>
            <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
              <SettingsIcon size={18} />
              <span>Settings</span>
            </div>
          </nav>
        </div>

        <div className="sidebar-profile">
          <div className="profile-avatar">
            <User size={18} />
          </div>
          <div className="profile-info">
            <span className="profile-name">{preferences.user_name || 'Mohammad'}</span>
            <span className="profile-role">Productivity Mode</span>
          </div>
        </div>
      </aside>

      {/* Main Panel Content Area */}
      <main className="main-content">
        <header className="header">
          <h1 className="header-title">
            {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
          </h1>
          <div className="header-actions">
            <button className="glass-button" style={{ padding: '8px 14px' }} onClick={handleNewTaskClick}>
              <Plus size={16} />
              <span>New Task</span>
            </button>
            <button className="glass-button-secondary" style={{ padding: '8px 14px' }} onClick={() => setShowHabitModal(true)}>
              <Award size={16} />
              <span>New Habit</span>
            </button>
            <div className="notification-bell">
              <Bell size={18} />
              {(overdueTasksCount > 0 || unreadNotifications > 0) && <span className="notification-dot"></span>}
            </div>
          </div>
        </header>

        <div className="content-body">
          {/* Proactive Banner Section */}
          {overdueTasksCount > 0 && (
            <div className="proactive-banner">
              <AlertTriangle className="banner-icon" size={20} />
              <div className="banner-content">
                <h4 className="banner-title">Accountability Alert</h4>
                <p className="banner-desc">You have {overdueTasksCount} overdue task{overdueTasksCount > 1 ? 's' : ''} currently holding up your progress. Would you like Nova to recommend a quick recovery reschedule?</p>
                <div className="banner-actions">
                  <button className="banner-btn" onClick={() => handleAlertBannerAction('overdue')}>Reschedule Overdue</button>
                </div>
              </div>
            </div>
          )}

          {conflicts.length > 0 && (
            <div className="proactive-banner" style={{ borderColor: 'rgba(245, 158, 11, 0.3)', background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.02) 100%)' }}>
              <Clock className="banner-icon" style={{ color: 'var(--color-warning)' }} size={20} />
              <div className="banner-content">
                <h4 className="banner-title" style={{ color: 'var(--color-warning)' }}>Scheduling Overlap Detected</h4>
                <p className="banner-desc">You have {conflicts.length} overlapping slot{conflicts.length > 1 ? 's' : ''} in your schedule. Proactively reorganize slots using AI assistance.</p>
                <div className="banner-actions">
                  <button className="banner-btn" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fde047', borderColor: 'rgba(245, 158, 11, 0.3)' }} onClick={() => handleAlertBannerAction('conflict')}>Resolve Schedule</button>
                </div>
              </div>
            </div>
          )}

          {/* Render Tab Views */}
          {activeTab === 'dashboard' && renderDashboard()}
          {activeTab === 'calendar' && renderCalendar()}
          {activeTab === 'tasks' && renderTasks()}
          {activeTab === 'goals' && renderGoals()}
          {activeTab === 'chat' && renderChat()}
          {activeTab === 'settings' && renderSettings()}
        </div>
      </main>

      {/* --- Modals --- */}
      {showTaskModal && renderTaskFormModal()}
      {showGoalModal && renderGoalFormModal()}
      {showHabitModal && renderHabitFormModal()}
      {showMemoryModal && renderMemoryFormModal()}
      {showConfirmModal && renderConfirmActionModal()}
    </div>
  );

  // --- Sub-render Views ---

  function renderDashboard() {
    return (
      <div className="dashboard-grid animate-slide">
        <div>
          {/* Stats Bar */}
          <div className="stat-cards">
            <div className="stat-card glass-card">
              <div className="stat-icon-wrapper" style={{ background: 'rgba(147, 51, 234, 0.12)', color: 'var(--accent-primary)' }}>
                <ListTodo size={20} />
              </div>
              <div className="stat-info">
                <span className="stat-val">{pendingTasks}</span>
                <span className="stat-label">Pending</span>
              </div>
            </div>
            <div className="stat-card glass-card">
              <div className="stat-icon-wrapper" style={{ background: 'rgba(16, 185, 129, 0.12)', color: 'var(--color-success)' }}>
                <CheckCircle2 size={20} />
              </div>
              <div className="stat-info">
                <span className="stat-val">{completedTasks}</span>
                <span className="stat-label">Completed</span>
              </div>
            </div>
            <div className="stat-card glass-card">
              <div className="stat-icon-wrapper" style={{ background: 'rgba(6, 182, 212, 0.12)', color: 'var(--color-info)' }}>
                <BarChart2 size={20} />
              </div>
              <div className="stat-info">
                <span className="stat-val">{successRate}%</span>
                <span className="stat-label">Success Rate</span>
              </div>
            </div>
            <div className="stat-card glass-card">
              <div className="stat-icon-wrapper" style={{ background: 'rgba(37, 99, 235, 0.12)', color: 'var(--accent-secondary)' }}>
                <Target size={20} />
              </div>
              <div className="stat-info">
                <span className="stat-val">{goals.length}</span>
                <span className="stat-label">Goals</span>
              </div>
            </div>
          </div>

          {/* Main Daily Dashboard checklist */}
          <div className="dashboard-section glass-card">
            <div className="section-header">
              <h3 className="section-title"><CheckSquare size={18} /> Today's Focus Checklist</h3>
              <button className="glass-button-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={fetchData}>
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
            <div className="tasks-list-container">
              {tasks.filter(t => t.status === 'pending').slice(0, 5).map(t => (
                <div key={t.id} className={`task-item ${t.status === 'completed' ? 'completed' : ''}`}>
                  <div className="task-left">
                    <div className="checkbox-wrapper" onClick={() => toggleTaskStatus(t)}>
                      <div className="checkbox-custom"></div>
                    </div>
                    <div className="task-details">
                      <span className="task-title">{t.title}</span>
                      <div className="task-meta">
                        <span className="badge badge-category">{t.category}</span>
                        <span className={`badge badge-priority-${t.priority}`}>{t.priority}</span>
                        {t.due_date && <span className="task-date"><Clock size={11} style={{ verticalAlign: 'text-bottom', marginRight: '2px' }} /> {new Date(t.due_date).toLocaleDateString()}</span>}
                      </div>
                    </div>
                  </div>
                  <button className="glass-button-secondary" style={{ padding: '6px', borderRadius: '8px', marginRight: '4px' }} onClick={() => handleEditTask(t)}>
                    <Edit size={14} color="var(--text-secondary)" />
                  </button>
                  <button className="glass-button-secondary" style={{ padding: '6px', borderRadius: '8px' }} onClick={() => handleDeleteTask(t)}>
                    <Trash2 size={14} color="var(--color-danger)" />
                  </button>
                </div>
              ))}
              {tasks.filter(t => t.status === 'pending').length === 0 && (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>All caught up! Let's schedule more tasks using the AI chat.</p>
              )}
            </div>
          </div>

          <div className="dashboard-section glass-card">
            <div className="section-header">
              <h3 className="section-title"><CalendarIcon size={18} /> Today's Planned Schedule</h3>
            </div>
            <div className="tasks-list-container">
              {todaySchedule.slice(0, 5).map(t => (
                <div key={`schedule-${t.id}`} className="task-item">
                  <div className="task-left">
                    <div className="task-details">
                      <span className="task-title">{t.title}</span>
                      <div className="task-meta">
                        <span className="badge badge-category">{t.category}</span>
                        <span className={`badge badge-priority-${t.priority}`}>{t.priority}</span>
                        <span className="task-date">
                          <Clock size={11} style={{ verticalAlign: 'text-bottom', marginRight: '2px' }} />
                          {new Date(t.scheduled_time || t.due_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {todaySchedule.length === 0 && (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>Nothing is scheduled today yet. Nova can auto-plan your next work block.</p>
              )}
            </div>
          </div>

          <div className="dashboard-section glass-card">
            <div className="section-header">
              <h3 className="section-title"><Award size={18} /> Habit Momentum</h3>
              <button className="glass-button-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => setShowHabitModal(true)}>
                <Plus size={12} /> Add Habit
              </button>
            </div>
            <div className="tasks-list-container">
              {habits.slice(0, 4).map(habit => (
                <div key={habit.id} className="task-item">
                  <div className="task-left">
                    <div className="task-details">
                      <span className="task-title">{habit.title}</span>
                      <div className="task-meta">
                        <span className="badge badge-category">{habit.frequency}</span>
                        <span style={{ color: 'var(--color-warning)' }}>Current streak: {habit.streak_current || 0}</span>
                        <span style={{ color: 'var(--text-muted)' }}>Best: {habit.streak_best || 0}</span>
                      </div>
                    </div>
                  </div>
                  <button className="glass-button-secondary" style={{ padding: '6px 10px' }} onClick={() => handleHabitCheckIn(habit)}>
                    Check In
                  </button>
                </div>
              ))}
              {habits.length === 0 && (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>No habits yet. Add one and Nova will coach your consistency.</p>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar recommendations */}
        <aside className="dashboard-sidebar">
          <div className="dashboard-section glass-card" style={{ height: '100%' }}>
            <h3 className="section-title" style={{ marginBottom: '16px' }}><Zap size={18} style={{ color: 'var(--color-warning)' }} /> Recommended Next</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>Nova's automated prioritization logic recommends these tasks next:</p>
            <div className="recommendations-container" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {recommendations.slice(0, 3).map(r => (
                <div key={r.id} className="glass-card" style={{ padding: '14px', background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <h5 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '6px' }}>{r.title}</h5>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '11px' }}>
                    <span className={`badge badge-priority-${r.priority}`}>{r.priority}</span>
                    <span style={{ color: 'var(--text-muted)' }}>Score: {r.recommendation_score}</span>
                  </div>
                </div>
              ))}
              {recommendations.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center' }}>No recommendations available right now.</p>
              )}
            </div>

            <div style={{ marginTop: '20px', paddingTop: '18px', borderTop: '1px solid var(--border-glass)' }}>
              <h4 style={{ fontSize: '13px', marginBottom: '10px' }}>Weekly Review Snapshot</h4>
              <div style={{ display: 'grid', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                <span>Completion rate: {review.summary?.completion_rate || 0}%</span>
                <span>Completed tasks: {review.summary?.completed_count || 0}</span>
                <span>Missed tasks: {review.summary?.missed_count || 0}</span>
                <span>Top focus: {review.summary?.top_category || 'None yet'}</span>
              </div>
            </div>

            <div style={{ marginTop: '20px', paddingTop: '18px', borderTop: '1px solid var(--border-glass)' }}>
              <h4 style={{ fontSize: '13px', marginBottom: '10px' }}>AI Coach Score</h4>
              <div style={{ fontSize: '30px', fontWeight: '700', marginBottom: '10px' }}>{coachReport.productivity_score || 0}</div>
              <div style={{ display: 'grid', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {(coachReport.personalized_recommendations || []).slice(0, 3).map((tip, index) => (
                  <span key={index}>{tip}</span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '20px', paddingTop: '18px', borderTop: '1px solid var(--border-glass)' }}>
              <div className="section-header" style={{ marginBottom: '10px' }}>
                <h4 style={{ fontSize: '13px' }}>Live Notifications</h4>
              </div>
              <div style={{ display: 'grid', gap: '10px' }}>
                {notifications.slice(0, 3).map(note => (
                  <div key={note.id} style={{ padding: '10px 12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ fontSize: '12px', fontWeight: '600' }}>{note.title}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{note.message}</div>
                  </div>
                ))}
                {notifications.length === 0 && (
                  <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>No pending notifications right now.</p>
                )}
              </div>
            </div>

            <div style={{ marginTop: '20px', paddingTop: '18px', borderTop: '1px solid var(--border-glass)' }}>
              <div className="section-header" style={{ marginBottom: '10px' }}>
                <h4 style={{ fontSize: '13px' }}>Long-Term Memory</h4>
                <button className="glass-button-secondary" style={{ padding: '6px 10px', fontSize: '11px' }} onClick={() => setShowMemoryModal(true)}>
                  Save
                </button>
              </div>
              <div style={{ display: 'grid', gap: '10px' }}>
                {memories.slice(0, 3).map(memory => (
                  <div key={memory.id} style={{ padding: '10px 12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{memory.memory_type}</div>
                    <div style={{ fontSize: '12px' }}>{memory.content}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </div>
    );
  }

  function renderTasks() {
    // Build filter list from DB categories; always show "All" first
    const catNames = categories.map(c => c.name);
    // Also collect any category names currently on tasks but not yet in DB (orphans from old data)
    tasks.forEach(t => {
      if (t.category && !catNames.includes(t.category)) catNames.push(t.category);
    });
    const filterLabels = ['All', ...catNames.sort()];

    const filtered = tasks.filter(t => {
      const matchCat = selectedTaskCategory === 'All' || t.category === selectedTaskCategory;
      const matchStatus = t.status === taskStatusFilter;
      return matchCat && matchStatus;
    });

    // ---- category manager local state helpers (via closure over component state) ----
    // We use a tiny inline component approach: store editing state in the parent via
    // a separate state pair declared at top level. Since we can't call useState here,
    // we read from `catMgrState` declared above.
    const [newCatInput, setNewCatInput] = catMgrState;
    const [renamingId, setRenamingId] = renamingState;
    const [renameVal, setRenameVal] = renameValState;

    const handleAddCategory = async () => {
      const name = newCatInput.trim();
      if (!name) return;
      const res = await fetch(`${API_BASE}/categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setNewCatInput('');
        await fetchData();
      }
    };

    const handleStartRename = (cat) => {
      setRenamingId(cat.id);
      setRenameVal(cat.name);
    };

    const handleSaveRename = async (cat) => {
      if (!renameVal.trim() || renameVal.trim() === cat.name) {
        setRenamingId(null);
        return;
      }
      const res = await fetch(`${API_BASE}/categories/${cat.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameVal.trim() })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setRenamingId(null);
        if (selectedTaskCategory === cat.name) setSelectedTaskCategory(renameVal.trim());
        await fetchData();
      }
    };

    const handleDeleteCategory = async (cat) => {
      triggerConfirmModal(
        `Delete category "${cat.name}"? Tasks using it will keep their current category label.`,
        async () => {
          await fetch(`${API_BASE}/categories/${cat.id}`, { method: 'DELETE' });
          if (selectedTaskCategory === cat.name) setSelectedTaskCategory('All');
          await fetchData();
        }
      );
    };

    return (
      <div className="animate-slide" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

        {/* Category Manager */}
        <div className="glass-card dashboard-section" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>📂 My Categories</h4>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                className="glass-input"
                style={{ padding: '5px 10px', fontSize: '12px', width: '160px' }}
                placeholder="New category name…"
                value={newCatInput}
                onChange={e => setNewCatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddCategory()}
              />
              <button className="glass-button" style={{ padding: '5px 12px', fontSize: '12px' }} onClick={handleAddCategory}>
                + Add
              </button>
            </div>
          </div>
          {categories.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>
              No categories yet. Create one above and select it when adding tasks.
            </p>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {categories.map(cat => (
                <div key={cat.id} style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-glass)', borderRadius: '8px', padding: '4px 10px' }}>
                  {renamingId === cat.id ? (
                    <input
                      className="glass-input"
                      style={{ padding: '2px 6px', fontSize: '12px', width: '110px' }}
                      value={renameVal}
                      onChange={e => setRenameVal(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') handleSaveRename(cat); if (e.key === 'Escape') setRenamingId(null); }}
                      autoFocus
                    />
                  ) : (
                    <span style={{ fontSize: '12px' }}>{cat.name}</span>
                  )}
                  {renamingId === cat.id ? (
                    <button onClick={() => handleSaveRename(cat)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-success)', fontSize: '13px' }} title="Save">✓</button>
                  ) : (
                    <button onClick={() => handleStartRename(cat)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '12px' }} title="Rename">✏️</button>
                  )}
                  <button onClick={() => handleDeleteCategory(cat)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-danger)', fontSize: '12px' }} title="Delete">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Task List */}
        <div className="glass-card dashboard-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border-glass)', paddingBottom: '16px', marginBottom: '16px' }}>
            {/* Status buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <button className={`glass-button${taskStatusFilter !== 'pending' ? '-secondary' : ''}`} style={{ padding: '8px 16px', fontSize: '13px' }} onClick={() => setTaskStatusFilter('pending')}>
                Pending
              </button>
              <button className={`glass-button${taskStatusFilter !== 'completed' ? '-secondary' : ''}`} style={{ padding: '8px 16px', fontSize: '13px' }} onClick={() => setTaskStatusFilter('completed')}>
                Completed
              </button>
            </div>

            {/* Category filter tabs — dynamic */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {filterLabels.map(cat => (
                <button
                  key={cat}
                  className="glass-button-secondary"
                  style={{ padding: '6px 12px', fontSize: '12px', borderColor: selectedTaskCategory === cat ? 'var(--accent-primary)' : '' }}
                  onClick={() => setSelectedTaskCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="tasks-list-container">
            {filtered.map(t => (
              <div key={t.id} className={`task-item ${t.status === 'completed' ? 'completed' : ''}`}>
                <div className="task-left">
                  <div className="checkbox-wrapper" onClick={() => toggleTaskStatus(t)}>
                    <div className="checkbox-custom"></div>
                  </div>
                  <div className="task-details">
                    <span className="task-title">{t.title}</span>
                    {t.description && <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{t.description}</span>}
                    <div className="task-meta">
                      <span className="badge badge-category">{t.category}</span>
                      <span className={`badge badge-priority-${t.priority}`}>{t.priority}</span>
                      {t.scheduled_time && <span style={{ color: 'var(--color-info)' }}><Clock size={11} style={{ marginRight: '3px' }} /> Scheduled: {new Date(t.scheduled_time).toLocaleString()}</span>}
                    </div>
                  </div>
                </div>
                <button className="glass-button-secondary" style={{ padding: '6px', borderRadius: '8px', marginRight: '4px' }} onClick={() => handleEditTask(t)}>
                  <Edit size={14} color="var(--text-secondary)" />
                </button>
                <button className="glass-button-secondary" style={{ padding: '6px', borderRadius: '8px' }} onClick={() => handleDeleteTask(t)}>
                  <Trash2 size={14} color="var(--color-danger)" />
                </button>
              </div>
            ))}
            {filtered.length === 0 && (
              <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>No tasks found matching these filters.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderGoals() {
    return (
      <div className="animate-slide">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '20px' }}>
          <button className="glass-button" onClick={() => setShowGoalModal(true)}>
            <Plus size={16} /> Add Long-term Goal
          </button>
        </div>

        <div className="goals-grid">
          {goals.map(g => (
            <div key={g.id} className="goal-card glass-card">
              <h3 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>{g.title}</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', minHeight: '40px', marginBottom: '12px' }}>{g.description}</p>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                <span>Category: {g.category}</span>
                <span>{g.progress_percent}% Complete</span>
              </div>
              
              <div className="goal-progress-bar-bg">
                <div className="goal-progress-bar-fg" style={{ width: `${g.progress_percent}%` }}></div>
              </div>

              <div style={{ display: 'flex', justify: 'space-between', marginTop: '16px', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span>{g.completed_tasks} of {g.total_tasks} Tasks finished</span>
                {g.target_date && <span>Target: {new Date(g.target_date).toLocaleDateString()}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  function renderCalendar() {
    const calendarYear = calendarCursor.getFullYear();
    const calendarMonth = calendarCursor.getMonth();
    const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const firstDayOffset = new Date(calendarYear, calendarMonth, 1).getDay();
    const calendarCells = [];

    for (let i = 0; i < firstDayOffset; i++) {
      calendarCells.push({ dayNum: null, currentMonth: false });
    }

    for (let day = 1; day <= daysInMonth; day++) {
      calendarCells.push({ dayNum: day, currentMonth: true });
    }

    const getTasksForDay = (day) => {
      if (!day) return [];
      const dayStr = `${calendarYear}-${String(calendarMonth + 1).padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
      // Match tasks by scheduled_time first, fall back to due_date if scheduled_time is null
      return tasks.filter(t => {
        const dateField = t.scheduled_time || t.due_date;
        return dateField && dateField.startsWith(dayStr);
      });
    };

    return (
      <div className="calendar-view animate-slide">
        <div className="calendar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="glass-button-secondary" type="button" onClick={() => setCalendarCursor(new Date(calendarYear, calendarMonth - 1, 1))}>Prev</button>
            <h3 style={{ fontSize: '18px', fontWeight: '700' }}>
              {calendarCursor.toLocaleString([], { month: 'long', year: 'numeric' })}
            </h3>
            <button className="glass-button-secondary" type="button" onClick={() => setCalendarCursor(new Date(calendarYear, calendarMonth + 1, 1))}>Next</button>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Live schedule from the task database. {reminders.length} active reminder{reminders.length === 1 ? '' : 's'} tracked.</span>
        </div>

        <div className="calendar-grid">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(label => (
            <div key={label} className="calendar-day-label">{label}</div>
          ))}
          
          {calendarCells.map((cell, idx) => {
            const dayTasks = getTasksForDay(cell.dayNum);
            const isToday = cell.dayNum === now.getDate() && calendarMonth === now.getMonth() && calendarYear === now.getFullYear();
            return (
              <div key={idx} className={`calendar-cell ${cell.currentMonth ? 'current-month' : 'other-month'} ${isToday ? 'today' : ''}`}>
                <span className="day-number">{cell.dayNum}</span>
                <div className="cell-events">
                  {dayTasks.map(t => (
                    <div key={t.id} className="calendar-event-badge" style={{ background: t.priority === 'high' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(147, 51, 234, 0.2)', color: t.priority === 'high' ? '#fca5a5' : '#c084fc' }}>
                      {t.title}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderChat() {
    return (
      <div className="chat-tab-container animate-slide">
        <div className="chat-box">
          <div className="chat-header">
            <div className="brand-icon" style={{ width: '32px', height: '32px', borderRadius: '8px' }}>
              <Zap size={16} color="#fff" />
            </div>
            <div className="chat-agent-info">
              <span className="chat-agent-name">Nova</span>
              <span className="chat-agent-status">Online • Accountability Assistant</span>
            </div>
          </div>

          <div className="chat-history">
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', padding: '12px 18px 0' }}>
              <button className="glass-button-secondary" type="button" style={{ padding: '8px 12px', fontSize: '12px' }} onClick={() => setChatInput('Nova, give me my daily review and tell me what to focus on next.')}>Daily Review</button>
              <button className="glass-button-secondary" type="button" style={{ padding: '8px 12px', fontSize: '12px' }} onClick={() => setChatInput('Nova, summarize my weekly productivity and coaching advice.')}>Weekly Coaching</button>
              <button className="glass-button-secondary" type="button" style={{ padding: '8px 12px', fontSize: '12px' }} onClick={() => setChatInput('Nova, use my saved memory and active goals to recommend my next step.')}>Use Memory</button>
            </div>
            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <div className="message-content">
                  {msg.text}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="chat-message assistant">
                <div className="message-content" style={{ color: 'var(--text-muted)' }}>Nova is typing...</div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form className="chat-input-area" onSubmit={handleSendMessage}>
            <textarea 
              className="chat-textarea" 
              placeholder="Ask Nova to schedule tasks, plan your week, or check goals progress..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(e);
                }
              }}
            />
            <button className="glass-button" type="submit" style={{ height: '48px' }}>
              <ArrowRight size={18} />
            </button>
          </form>
          <div style={{ padding: '0 18px 18px', display: 'grid', gap: '8px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Recent memory and coach context</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {memories.slice(0, 3).map(memory => (
                <span key={memory.id} className="badge badge-category" style={{ maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {memory.content}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  function renderSettings() {
    const handleSetPref = async (key, val) => {
      try {
        await fetch(`${API_BASE}/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value: JSON.stringify(val) })
        });
        fetchData();
      } catch (err) {
        console.error('Error saving preference:', err);
      }
    };

    return (
      <div className="glass-card dashboard-section animate-slide" style={{ maxWidth: '600px' }}>
        <h3 className="section-title" style={{ marginBottom: '24px' }}><SettingsIcon size={18} /> Personal Preferences</h3>
        
        <div className="form-group">
          <label className="form-label">User Name</label>
          <input 
            className="glass-input" 
            type="text" 
            defaultValue={preferences.user_name || 'Mohammad'} 
            onBlur={(e) => handleSetPref('user_name', e.target.value)}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Working Hours Start</label>
            <input 
              className="glass-input" 
              type="time" 
              defaultValue={preferences.work_start || '09:00'} 
              onBlur={(e) => handleSetPref('work_start', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Working Hours End</label>
            <input 
              className="glass-input" 
              type="time" 
              defaultValue={preferences.work_end || '18:00'} 
              onBlur={(e) => handleSetPref('work_end', e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Focus Area Categories</label>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
            {['DSA', 'Machine Learning', 'Communication', 'Fitness', 'Personal'].map(cat => (
              <button
                key={cat}
                type="button"
                className="badge badge-category"
                style={{
                  padding: '6px 12px',
                  fontSize: '11px',
                  border: preferences.focus_categories?.includes(cat) ? '1px solid var(--accent-primary)' : '1px solid transparent',
                  background: preferences.focus_categories?.includes(cat) ? 'rgba(147, 51, 234, 0.18)' : undefined,
                  cursor: 'pointer'
                }}
                onClick={() => {
                  const current = preferences.focus_categories || [];
                  const next = current.includes(cat)
                    ? current.filter(item => item !== cat)
                    : [...current, cat];
                  handleSetPref('focus_categories', next);
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '24px' }}>Preferences are saved directly to the local SQLite database and are persisted across restarts.</p>
      </div>
    );
  }

  // --- Modal Element Renders ---

  function renderTaskFormModal() {
    return (
      <div className="modal-overlay">
        <div className="modal-content">
          <div className="modal-title">
            {editingTaskId ? <Edit size={20} /> : <Plus size={20} />}
            <span>{editingTaskId ? 'Edit Task' : 'Create New Task'}</span>
          </div>
          <form onSubmit={handleTaskFormSubmit}>
            <div className="form-group">
              <label className="form-label">Task Title</label>
              <input className="glass-input" type="text" required value={taskForm.title} onChange={e => setTaskForm({...taskForm, title: e.target.value})} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input className="glass-input" type="text" value={taskForm.description} onChange={e => setTaskForm({...taskForm, description: e.target.value})} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Category</label>
                <select
                  className="glass-input"
                  value={taskForm.category}
                  onChange={e => setTaskForm({...taskForm, category: e.target.value, newCategoryName: ''})}
                >
                  <option value="">-- Select category --</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                  <option value="__new__">+ Create new category…</option>
                </select>
                {taskForm.category === '__new__' && (
                  <input
                    className="glass-input"
                    style={{ marginTop: '6px' }}
                    placeholder="Type new category name"
                    value={taskForm.newCategoryName}
                    onChange={e => setTaskForm({...taskForm, newCategoryName: e.target.value})}
                  />
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Priority</label>
                <select className="glass-input" value={taskForm.priority} onChange={e => setTaskForm({...taskForm, priority: e.target.value})}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Due Date</label>
                <input className="glass-input" type="date" value={taskForm.due_date} onChange={e => setTaskForm({...taskForm, due_date: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Goal (Optional)</label>
                <select className="glass-input" value={taskForm.goal_id} onChange={e => setTaskForm({...taskForm, goal_id: e.target.value})}>
                  <option value="">None</option>
                  {goals.map(g => (
                    <option key={g.id} value={g.id}>{g.title}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Scheduled Start Slot</label>
                <input className="glass-input" type="datetime-local" value={taskForm.scheduled_time} onChange={e => setTaskForm({...taskForm, scheduled_time: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Duration (Minutes)</label>
                <input className="glass-input" type="number" value={taskForm.duration} onChange={e => setTaskForm({...taskForm, duration: e.target.value})} />
              </div>
            </div>
            {editingTaskId && (
              <div className="form-group">
                <label className="form-label">Status</label>
                <select className="glass-input" value={taskForm.status} onChange={e => setTaskForm({...taskForm, status: e.target.value})}>
                  <option value="pending">Pending</option>
                  <option value="completed">Completed</option>
                  <option value="missed">Missed</option>
                </select>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Reminder Time (Optional)</label>
              <input className="glass-input" type="datetime-local" value={taskForm.reminder_time} onChange={e => setTaskForm({...taskForm, reminder_time: e.target.value})} />
            </div>

            <div className="modal-footer">
              <button className="glass-button-secondary" type="button" onClick={() => setShowTaskModal(false)}>Cancel</button>
              <button className="glass-button" type="submit">{editingTaskId ? 'Save Changes' : 'Create Task'}</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  function renderGoalFormModal() {
    return (
      <div className="modal-overlay">
        <div className="modal-content">
          <div className="modal-title">
            <Target size={20} />
            <span>Create Long-term Goal</span>
          </div>
          <form onSubmit={handleCreateGoal}>
            <div className="form-group">
              <label className="form-label">Goal Title</label>
              <input className="glass-input" type="text" required value={goalForm.title} onChange={e => setGoalForm({...goalForm, title: e.target.value})} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input className="glass-input" type="text" value={goalForm.description} onChange={e => setGoalForm({...goalForm, description: e.target.value})} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Category</label>
                <select
                  className="glass-input"
                  value={goalForm.category}
                  onChange={e => setGoalForm({...goalForm, category: e.target.value, newCategoryName: ''})}
                >
                  <option value="">-- Select category --</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                  <option value="__new__">+ Create new category…</option>
                </select>
                {goalForm.category === '__new__' && (
                  <input
                    className="glass-input"
                    style={{ marginTop: '6px' }}
                    placeholder="Type new category name"
                    value={goalForm.newCategoryName}
                    onChange={e => setGoalForm({...goalForm, newCategoryName: e.target.value})}
                  />
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Target Deadline</label>
                <input className="glass-input" type="date" value={goalForm.target_date} onChange={e => setGoalForm({...goalForm, target_date: e.target.value})} />
              </div>
            </div>

            <div className="modal-footer">
              <button className="glass-button-secondary" type="button" onClick={() => setShowGoalModal(false)}>Cancel</button>
              <button className="glass-button" type="submit">Create Goal</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  function renderHabitFormModal() {
    return (
      <div className="modal-overlay">
        <div className="modal-content">
          <div className="modal-title">
            <Award size={20} />
            <span>Create Habit</span>
          </div>
          <form onSubmit={handleCreateHabit}>
            <div className="form-group">
              <label className="form-label">Habit Title</label>
              <input className="glass-input" type="text" required value={habitForm.title} onChange={e => setHabitForm({...habitForm, title: e.target.value})} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input className="glass-input" type="text" value={habitForm.description} onChange={e => setHabitForm({...habitForm, description: e.target.value})} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Category</label>
                <select
                  className="glass-input"
                  value={habitForm.category}
                  onChange={e => setHabitForm({...habitForm, category: e.target.value, newCategoryName: ''})}
                >
                  <option value="">-- Select category --</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                  <option value="__new__">+ Create new category…</option>
                </select>
                {habitForm.category === '__new__' && (
                  <input
                    className="glass-input"
                    style={{ marginTop: '6px' }}
                    placeholder="Type new category name"
                    value={habitForm.newCategoryName}
                    onChange={e => setHabitForm({...habitForm, newCategoryName: e.target.value})}
                  />
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Frequency</label>
                <select className="glass-input" value={habitForm.frequency} onChange={e => setHabitForm({...habitForm, frequency: e.target.value})}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Target Count</label>
                <input className="glass-input" type="number" min="1" value={habitForm.target_count} onChange={e => setHabitForm({...habitForm, target_count: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Linked Goal</label>
                <select className="glass-input" value={habitForm.goal_id} onChange={e => setHabitForm({...habitForm, goal_id: e.target.value})}>
                  <option value="">None</option>
                  {goals.map(g => (
                    <option key={g.id} value={g.id}>{g.title}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Start Date</label>
                <input className="glass-input" type="date" value={habitForm.start_date} onChange={e => setHabitForm({...habitForm, start_date: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Reminder Time</label>
                <input className="glass-input" type="datetime-local" value={habitForm.reminder_time} onChange={e => setHabitForm({...habitForm, reminder_time: e.target.value})} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="glass-button-secondary" type="button" onClick={() => setShowHabitModal(false)}>Cancel</button>
              <button className="glass-button" type="submit">Create Habit</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  function renderMemoryFormModal() {
    return (
      <div className="modal-overlay">
        <div className="modal-content">
          <div className="modal-title">
            <MessageSquare size={20} />
            <span>Save Long-Term Memory</span>
          </div>
          <form onSubmit={handleCreateMemory}>
            <div className="form-group">
              <label className="form-label">Memory</label>
              <textarea className="glass-input" rows="4" required value={memoryForm.content} onChange={e => setMemoryForm({...memoryForm, content: e.target.value})} />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="glass-input" value={memoryForm.memory_type} onChange={e => setMemoryForm({...memoryForm, memory_type: e.target.value})}>
                  <option value="context">Context</option>
                  <option value="preference">Preference</option>
                  <option value="lesson">Lesson</option>
                  <option value="achievement">Achievement</option>
                  <option value="obstacle">Obstacle</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Tags</label>
                <input className="glass-input" type="text" placeholder="focus, morning, work" value={memoryForm.tags} onChange={e => setMemoryForm({...memoryForm, tags: e.target.value})} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="glass-button-secondary" type="button" onClick={() => setShowMemoryModal(false)}>Cancel</button>
              <button className="glass-button" type="submit">Save Memory</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  function renderConfirmActionModal() {
    return (
      <div className="modal-overlay">
        <div className="modal-content" style={{ maxWidth: '400px' }}>
          <div className="modal-title" style={{ color: 'var(--color-danger)' }}>
            <AlertTriangle size={20} />
            <span>Confirm Action</span>
          </div>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
            {confirmAction?.message}
          </p>
          <div className="modal-footer">
            <button className="glass-button-secondary" type="button" onClick={() => setShowConfirmModal(false)}>Cancel</button>
            <button className="glass-button" style={{ background: 'var(--color-danger)' }} type="button" onClick={executeConfirmAction}>Confirm</button>
          </div>
        </div>
      </div>
    );
  }
}
