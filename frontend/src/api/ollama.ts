import type { OllamaModel } from '../types';

export const ollamaApi = {
  /**
   * Get the list of installed models
   */
  listModels: async (): Promise<OllamaModel[]> => {
    return window.api.listModels();
  },


  /**
   * Switch the active model
   */
  switchModel: async (model: string): Promise<unknown> => {
    return window.api.switchModel(model);
  },
};
