import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { requestAPI } from './handler';

/**
 * Initialization data for the qStore extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'qStore:plugin',
  description: 'A Custom YStore implementation',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension qStore is activated!');

    requestAPI<any>('get-example')
      .then(data => {
        console.log(data);
      })
      .catch(reason => {
        console.error(
          `The q_store server extension appears to be missing.\n${reason}`
        );
      });
  }
};

export default plugin;
