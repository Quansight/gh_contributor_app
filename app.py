import panel as pn
import pandas as pd
import ibis

def remove_sign_from_handles(twitter_handle):
    if type(twitter_handle) != str:
        return twitter_handle
    return twitter_handle[2:-1]

def load_twitter_data():
    df = pd.read_csv('data/users_clean.csv')
    df.columns = ['id', 'fullname', 'twitter_handle', 'private_account',
           'verified_account', 'bio', 'location', 'url', 'date_joined',
           'tweets', 'following', 'followers', 'likes', 'media',
           'avatar_url']

    df2 = pd.read_csv('data/users_clean_2nd_batch.csv')
    df2.columns = ['id', 'fullname', 'twitter_handle', 'private_account',
           'verified_account', 'bio', 'location', 'url', 'date_joined',
           'tweets', 'following', 'followers', 'likes', 'media',
           'avatar_url']
    twitter_data = pd.concat([df, df2]).reset_index().iloc[:,1:]
    twitter_data['twitter_handle_processed'] = twitter_data.twitter_handle.apply(remove_sign_from_handles)
    return twitter_data


class App:

    def __init__(self):

        self.db = ibis.sqlite.connect('data/contributors.db')
        repos = self.db.table('repositories')['id', 'name'].execute()
        self.repo_ids = {name.split('/')[-1]: id_num for name, id_num in zip(repos['name'], repos['id'])}


        self.twitter_data = load_twitter_data()
        self.setup_widgets()
        self.setup_layout()


    def setup_widgets(self):
        self.repo_input = pn.widgets.TextInput(placeholder='Enter a project name (i.e. dask)')
        self.button = pn.widgets.Button(name='Run',
                                        button_type='primary',
                                        width=200)
        self.button.on_click(self.click_update)

        self.warning_message = None
        self.warning_markdown = pn.pane.Markdown(self.warning_message, width=400)

        self.users_select = pn.widgets.Select(options=[], width=300)
        self.users_select.param.watch(self.update_user_data, 'value')
        self.users_select.param.watch(self.update_twitter_data, 'value')

        # info layout
        self.login = pn.pane.Markdown(width=400)
        self.email = pn.pane.Markdown(width=400)
        self.company = pn.pane.Markdown(width=400)
        self.github_url = pn.pane.Markdown(width=400)

        self.linkedin_search = pn.pane.HTML(height=50)

        self.twitter_bio = pn.pane.Markdown(width=400, height=40)
        self.twitter_handle = pn.pane.Markdown(width=400)
        self.location = pn.pane.Markdown(width=400)
        self.twitter_url = pn.pane.Markdown(width=400)



    def check_input(self):
        if self.repo_input.value not in self.repo_ids:
            self.warning_message = 'No data found for that project.'
            return False
        else:
            self.warning_message = None
            return True

    def click_update(self, event):
        valid_request = self.check_input()
        self.warning_markdown.object = self.warning_message
        self.update_layout(valid_request)

        if not valid_request:
            return

        self.get_project_users()
        self.get_display_names()
        self.users_select.options = self.display_names
        self.full_layout = True

    def get_project_users(self):
        repo_users = self.db.table('repository_users')
        self.project_users = repo_users.filter(repo_users['repository_id'] == self.repo_ids[self.repo_input.value]).execute()

    def get_display_names(self):
        users_table = self.db.table('users')
        sorted_users = self.project_users.sort_values('total_commits', ascending=False)
        reindex = sorted_users.index
        filtered = users_table['id'].isin(self.project_users.user_id)
        self.filtered_data = users_table[filtered]
        sorted_data = self.filtered_data.execute().iloc[reindex,:]
        names = sorted_data[['name', 'login']]
        self.display_names = [' '.join((name, f'({login}) {n_commits}')) if name is not None else f'{login} {n_commits}' for name,
                         login, n_commits in zip(names['name'], names['login'], sorted_users['total_commits'])]

    def get_user_data(self):
        if '(' in self.users_select.value:
            start = self.users_select.value.find('(') + 1
            end = self.users_select.value.find(')')
            current_login = self.users_select.value[start:end]

        else:
            current_login = self.users_select.value.split(' ')[0]
        self.user_data = self.filtered_data.filter(self.filtered_data['login'] == current_login).execute()


    def update_project(self, event):
        self.get_project_users()
        self.get_display_names()
        self.users_select.options = self.display_names

    def update_user_data(self, event):
        self.get_user_data()
        self.login.object = f"**Login:** {self.user_data['login'][0]}"
        self.email.object = f"**Email:** {self.user_data['email'][0]}"
        self.company.object = f"**Company:** {self.user_data['company'][0]}"
        gh_url = self.user_data['github_url'][0]
        self.github_url.object = f"**Github_url:** [{gh_url}]({gh_url})"
        if self.user_data.name[0] is not None:
            names = self.user_data.name[0].split(' ')
            query_link = f'https://www.bing.com/search?q='
            for n in names: query_link += f'{n}+'
            query_link += f'{self.repo_input.value}+'
            query_link += 'linkedin'
        else:
            query_link = f'https://www.bing.com/search?q={self.user_data.login[0]}+{self.repo_input.value}+linkedin'
        iframe = f"""
        <iframe width="500%" height="2300%" src="{query_link}"
        frameborder="0" scrolling="yes" marginheight="0" marginwidth="0"></iframe>
        """
        self.linkedin_search.object = iframe

    def update_twitter_data(self, event):

        if self.user_data.twitter[0] is None:
            self.display_twitter_data = None
            if self.twitter_layout in self.markdown_layout.objects:
                self.markdown_layout.remove(self.twitter_layout)
            return

        else:
            self.display_twitter_data = self.twitter_data[self.twitter_data.twitter_handle_processed.isin([self.user_data.twitter[0]])]
            if self.display_twitter_data.shape[0] == 0:
                if self.twitter_layout in self.markdown_layout.objects:
                    self.markdown_layout.remove(self.twitter_layout)
                return
            if self.twitter_layout not in self.markdown_layout.objects:
                self.markdown_layout.append(self.twitter_layout)

        self.twitter_bio.object = f"**Twitter Bio:** {self.display_twitter_data.bio.tolist()[0]}"
        self.twitter_handle.object = f"**Twitter Handle:** {self.display_twitter_data.twitter_handle.tolist()[0]}"
        self.location.object = f"**Twitter Location:** {self.display_twitter_data.location.tolist()[0]}"
        url = self.display_twitter_data.url.tolist()[0]
        self.twitter_url.object = f"**Twitter URL:** [{url}]({url})"

    def setup_layout(self):
        self.twitter_layout = pn.Column(self.twitter_bio, self.twitter_handle, self.location,
                                       self.twitter_url)
        self.markdown_layout = pn.Column(self.users_select, self.login, self.email, self.company, self.github_url,
                                         self.twitter_layout, width=400)

        self.search_iframe = pn.Column(self.linkedin_search)
        self.input_row = pn.Row(self.repo_input, self.button)
        self.layout = pn.Column(self.input_row)
        self.whole_layout = pn.Row(self.layout,self.search_iframe)
        self.full_layout = False
        self.whole_layout.show()
        #self.whole_layout.servable()

    def update_layout(self, valid_request):


        if not valid_request:
            if not self.full_layout:
                if self.warning_markdown not in self.layout.objects:
                    self.layout.append(self.warning_markdown)
                else: return
            # full layout
            else:
                self.layout.remove(self.markdown_layout)
                self.layout.append(self.warning_markdown)
                self.search_iframe.remove(self.linkedin_search)

        else:
            if self.warning_markdown in self.layout.objects:
                self.layout.remove(self.warning_markdown)
            if self.markdown_layout not in self.layout.objects:
                self.layout.append(self.markdown_layout)
                self.search_iframe.append(self.linkedin_search)


if __name__.startswith("bokeh"):
    App().whole_layout.servable()